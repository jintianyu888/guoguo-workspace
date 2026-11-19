#!/usr/bin/env python3
"""incident-ledger.py — 网关重启/崩溃台账 + 每日归因自查
子命令:
  backfill [--days N]   从 journal 回填最近 N 天的网关重启事件（幂等，按 started_at 去重）
  append <json>         追加一条（gw-restart-notice.sh 调用）
  review [--hours N]    汇总归因，写 state/incidents/daily-<date>.txt，异常多则提示
台账: state/incidents/incidents.jsonl
"""
import json, os, re, subprocess, sys, datetime as dt

WS = "/home/j/.openclaw/workspace"
LEDGER = os.path.join(WS, "state/incidents/incidents.jsonl")
os.makedirs(os.path.dirname(LEDGER), exist_ok=True)

CLASS_RULES = [
    ("升级/schema 未迁移", [r"exit(ed)?\s+code=exited, status=78", r"schema", r"migration required", r"openclaw update"]),
    ("OOM/内存耗尽", [r"Out of memory", r"oom-kill", r"Killed process"]),
    ("SQLite 故障", [r"SQLITE_FULL", r"database or disk is full", r"SqliteWorkerError"]),
    ("计划内重启", [r"safe-restart", r"restart-gateway\.sh"]),
    ("插件/依赖异常", [r"plugin", r"Cannot find module", r"ERR_MODULE"]),
    ("端口占用", [r"EADDRINUSE", r"address already in use"]),
    ("未知崩溃", [r"Main process exited, code=exited, status=1"]),
]

def classify(text):
    for name, pats in CLASS_RULES:
        for p in pats:
            if re.search(p, text, re.I):
                return name
    return "其他/未分类"

def load():
    if not os.path.exists(LEDGER):
        return []
    out = []
    for line in open(LEDGER, encoding="utf-8"):
        line = line.strip()
        if line:
            try: out.append(json.loads(line))
            except Exception: pass
    return out

def append(rec):
    seen = {r.get("started_at") for r in load()}
    if rec.get("started_at") in seen:
        return False
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return True

def backfill(days=7):
    since = f"{days} days ago"
    j = subprocess.run(["journalctl", "--user", "-u", "openclaw-gateway", "--since", since,
                        "--no-pager", "-o", "short-iso"], capture_output=True, text=True).stdout
    lines = j.splitlines()
    added = 0
    last_exit = None
    for i, ln in enumerate(lines):
        if "Main process exited" in ln:
            last_exit = ln
        if "Started openclaw-gateway.service" in ln or "Started OpenClaw Gateway" in ln:
            ts = ln.split(" ")[0]
            ctx = "\n".join(lines[max(0, i - 25):i + 3])
            cls = classify(ctx)
            rec = {"started_at": ts, "source": "backfill", "class": cls,
                   "evidence": (last_exit or "")[:200]}
            if append(rec): added += 1
            last_exit = None
    return added

def review(hours=24):
    cutoff = dt.datetime.now() - dt.timedelta(hours=hours)
    recs = []
    for r in load():
        try:
            t = dt.datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))
        except Exception:
            continue
        if t.tzinfo: t = t.replace(tzinfo=None)
        if t >= cutoff:
            if not r.get("class"):
                r["class"] = classify((r.get("evidence") or "") + " " + (r.get("kind") or ""))
            recs.append(r)
    groups = {}
    for r in recs:
        groups.setdefault(r.get("class", "其他/未分类"), []).append(r)
    out = [f"网关重启/崩溃复盘 · 最近 {hours} 小时 · 共 {len(recs)} 次", ""]
    if not recs:
        out.append("无重启事件。")
    for cls, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        out.append(f"- {cls}: {len(items)} 次（最近 {items[-1]['started_at']}）")
        ev = (items[-1].get("evidence") or "").strip()
        if ev: out.append(f"  证据: {ev[:160]}")
    out.append("")
    out.append("预防建议（按次数优先）：")
    for cls, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        n = len(items)
        if n == 0: continue
        tip = {
            "升级/schema 未迁移": "升级前先跑 openclaw doctor --fix，并加升级前 schema 检查",
            "OOM/内存耗尽": "查堆外增长，限制单会话/子代理并发，必要时加 cgroup 内存上限",
            "SQLite 故障": "保持每小时 WAL checkpoint；worker 池打满即重启而非重试",
            "插件/依赖异常": "插件与核心版本对齐后再启用，升级后跑插件自检",
            "端口占用": "重启前检查 18789 占用者，残留进程先杀",
            "未知崩溃": "开启 crash 前 30 行日志留存，下次复现可定位",
        }.get(cls, "补充该类的判定规则与证据采集")
        out.append(f"- {cls} → {tip}")
    txt = "\n".join(out)
    path = os.path.join(WS, f"state/incidents/daily-{dt.date.today().isoformat()}.txt")
    open(path, "w", encoding="utf-8").write(txt + "\n")
    print(txt)
    print("\n写入: " + path)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "review"
    if cmd == "backfill":
        d = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 7
        print(f"回填新增 {backfill(d)} 条")
    elif cmd == "append":
        rec = json.loads(sys.argv[2])
        print("appended" if append(rec) else "duplicate")
    else:
        h = int(sys.argv[sys.argv.index("--hours") + 1]) if "--hours" in sys.argv else 24
        review(h)
