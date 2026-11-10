#!/usr/bin/env bash
# token-diet-check.sh —— 月度「提示词瘦身 / 任务整合」体检（零 token）（2026-10-01 任务四）
# 排期：每月 1 日 23:00（闲时）。正常静默；有问题才输出（announce 到飞书）。
# 检查项：
#   1) 各 agent 提示词体积（AGENTS/SOUL/USER/MEMORY/IDENTITY/DREAMS）与基线比较，暴涨告警
#   2) 定时任务清单：总数变化、失败项、重复名、高峰时段 agentTurn、过密频率
#   3) 汇总：只在有异常时打印
set -u
exec python3 - <<'PYEOF'
import json, os, subprocess, datetime, collections

W = "/home/j/.openclaw/workspace"
ST = os.path.join(W, "state", "token-diet")
os.makedirs(ST, exist_ok=True)
BASE = os.path.join(ST, "baseline.json")
REPORT = os.path.join(ST, "latest.md")
GROW_BYTES = 8192
GROW_PCT = 25
PROMPT_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "MEMORY.md", "IDENTITY.md", "DREAMS.md"]

old = {}
if os.path.isfile(BASE):
    try:
        old = json.load(open(BASE, encoding="utf-8"))
    except Exception:
        old = {}
prev_sizes = old.get("sizes", {}) or {}
prev_jobs = old.get("jobTotal")

alerts = []

# ---------- 1. 提示词体积 ----------
roots = {"main": W}
base_dir = "/home/j/.openclaw"
if os.path.isdir(base_dir):
    for name in sorted(os.listdir(base_dir)):
        p = os.path.join(base_dir, name)
        if name.startswith("workspace-") and os.path.isdir(p):
            roots[name[len("workspace-"):]] = p

cur = {}
for aid, root in roots.items():
    tot = 0
    for f in PROMPT_FILES:
        fp = os.path.join(root, f)
        if os.path.isfile(fp):
            s = os.path.getsize(fp)
            tot += s
            cur[aid + "/" + f] = s
    if tot:
        cur[aid + "/__total__"] = tot

for k, v in cur.items():
    if k.endswith("__total__"):
        continue
    ov = prev_sizes.get(k)
    if not isinstance(ov, int) or ov <= 0:
        continue
    if (v - ov) > GROW_BYTES and (v - ov) * 100.0 / ov > GROW_PCT:
        alerts.append("提示词暴涨 %s：%d → %d 字节 (+%.0f%%)" % (k, ov, v, (v - ov) * 100.0 / ov))

# ---------- 2. 任务清单 ----------
jobs = []
try:
    out = subprocess.run(["openclaw", "automations", "list", "--all", "--json"],
                         capture_output=True, text=True, timeout=180).stdout
    jobs = (json.loads(out) or {}).get("jobs", [])
except Exception as e:
    alerts.append("任务清单读取失败：%r" % (e,))

def sched_kind(s):
    k = (s or {}).get("kind")
    if k == "every":
        return "every %dmin" % ((s.get("everyMs") or 0) // 60000)
    if k == "cron":
        return "cron %s" % s.get("expr")
    if k == "at":
        return "at %s" % s.get("atMs")
    return str(k)

def hourset(h):
    s = set()
    if h == "*":
        return set(range(24))
    for seg in h.split(","):
        if "/" in seg:
            a, b = seg.split("/")
            base = list(range(24)) if a == "*" else [int(x) for x in a.split("-")][:1]
            if a == "*":
                return set(range(0, 24, int(b)))
            continue
        if "-" in seg:
            a, b = seg.split("-")
            try:
                s |= set(range(int(a), int(b) + 1))
            except Exception:
                pass
        else:
            try:
                s.add(int(seg))
            except Exception:
                pass
    return s

def peak_agentturn(expr):
    p = expr.split()
    if len(p) != 5:
        return False
    hour, dow = p[1], p[4]
    if not (hourset(hour) & (set(range(9, 12)) | set(range(14, 18)))):
        return False
    if dow == "*":
        return True
    days = set()
    for seg in dow.split(","):
        if "-" in seg:
            a, b = seg.split("-")
            try:
                days |= set(range(int(a), int(b) + 1))
            except Exception:
                pass
        else:
            try:
                days.add(int(seg))
            except Exception:
                pass
    return bool(days & {1, 2, 3, 4, 5})

total = len(jobs)
enabled = [j for j in jobs if j.get("enabled")]
names = collections.Counter(j.get("name") for j in jobs)
dups = {k: v for k, v in names.items() if v > 1}

failed = []
for j in enabled:
    st = j.get("lastRunStatus")
    if j.get("lastRunAtMs") and st and st != "ok":
        failed.append("%s(%s) → %s" % (j.get("name"), (j.get("id") or "")[:8], st))

peak = []
dense = []
for j in enabled:
    p = j.get("payload") or {}
    s = j.get("schedule") or {}
    if p.get("kind") == "agentTurn" and s.get("kind") == "cron" and peak_agentturn(s.get("expr") or ""):
        peak.append("%s(%s) %s" % (j.get("name"), (j.get("id") or "")[:8], s.get("expr")))
    if s.get("kind") == "every" and (s.get("everyMs") or 0) < 300000:
        dense.append("%s(%s) %s" % (j.get("name"), (j.get("id") or "")[:8], sched_kind(s)))

for k, v in sorted(dups.items()):
    alerts.append("重复任务名：%s ×%d" % (k, v))
if failed:
    alerts.append("任务失败：%s" % "；".join(failed))
if peak:
    alerts.append("agentTurn 排在高峰时段（应挪闲时）：%s" % "；".join(peak))
if dense:
    alerts.append("频率过密（<5 分钟）：%s" % "；".join(dense))
if prev_jobs is not None and total != prev_jobs:
    alerts.append("任务总数变化：%s → %s" % (prev_jobs, total))

# ---------- 3. 输出 ----------
lines = []
lines.append("# 月度瘦身体检 · %s" % datetime.datetime.now().strftime("%F %T"))
lines.append("")
lines.append("任务总数 %d（启用 %d）；提示词文件 %d 个" % (total, len(enabled), len([k for k in cur if not k.endswith("__total__")])))
lines.append("")
if alerts:
    lines.append("## ⚠️ 异常 %d 项" % len(alerts))
    for a in alerts:
        lines.append("- " + a)
else:
    lines.append("✅ 无异常")

open(REPORT, "w", encoding="utf-8").write("\n".join(lines) + "\n")

new = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "sizes": cur, "jobTotal": total}
json.dump(new, open(BASE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 只在有异常时向 announce 输出（正常 → 空输出 → 不打扰）
if alerts:
    print("📉 月度瘦身体检发现 %d 项异常：" % len(alerts))
    for a in alerts:
        print("· " + a)
    print("详见 %s" % REPORT)
PYEOF
