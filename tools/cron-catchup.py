#!/usr/bin/env python3
# cron-catchup.py v1.1 (2026-11-17) —— 开机漏档补跑（零 token 判定，串行执行）
# 判定以任务自身的 state.lastRunAtMs 为准（cron-miss.py 的判据有假阳性，不再采信它的 last）。
# 安全边界：只补简报/报告/体检/自审/汇总类；备份、镜像、推送、压缩、升级、重启、删除、外发一律不补。
# 用法：python3 tools/cron-catchup.py [--since-minutes 240] [--max 6] [--dry-run] [--force]
import argparse, datetime as dt, importlib.util, json, os, re, subprocess, sys

W = "/home/j/.openclaw/workspace"
LOG = os.path.join(W, "state/work/cron-catchup.log")
ALLOW = re.compile(r"简报|briefing|日报|report|体检|自审|汇总|审计|audit|扫描|summary|提醒|计划|盘点|巡检")
DENY = re.compile(r"备份|backup|镜像|mirror|推送|push|清理|clean|压缩|compact|升级|upgrade|重启|restart|删除|delete|演练|drill|归档|archive|下单|付款|发送|发布")

def say(m):
    line = "%s %s" % (dt.datetime.now().strftime("%F %T"), m)
    print(line)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def sh(args, timeout=180):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout
    except Exception as e:
        return 255, str(e)

def load_matcher():
    spec = importlib.util.spec_from_file_location("cron_miss", os.path.join(W, "tools/cron-miss.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since-minutes", type=int, default=240)
    ap.add_argument("--max", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--grace-minutes", type=int, default=12, help="应跑时刻距今不足这么多分钟就不补（防正在跑）")
    a = ap.parse_args()
    now = dt.datetime.now()
    since = now - dt.timedelta(minutes=a.since_minutes)
    say("=== catchup start since=%s max=%d dry=%s ===" % (since.strftime("%F %H:%M"), a.max, a.dry_run))

    if not a.force and now.weekday() < 5 and (9 <= now.hour < 12 or 14 <= now.hour < 18):
        say("工作日高峰时段，不补跑（避免烧 token）")
        return 0

    rc, jout = sh(["openclaw", "cron", "list", "--json"], 60)
    try:
        jobs = json.loads(jout).get("jobs", [])
    except Exception:
        say("✗ 取不到任务清单 rc=%s" % rc)
        return 0
    cm = load_matcher()

    picked, skipped = [], []
    for j in jobs:
        name = j.get("name") or ""
        if not j.get("enabled"): continue
        sch = j.get("schedule") or {}
        if sch.get("kind") != "cron": continue
        expr = (sch.get("expr") or "").strip()
        if not expr: continue
        if DENY.search(name): skipped.append((name, "重活/危险类")); continue
        if not ALLOW.search(name): skipped.append((name, "不在补跑白名单")); continue
        try:
            exp = cm.last_fire(expr, now, 26)
        except Exception:
            skipped.append((name, "表达式解析失败")); continue
        if exp is None or exp < since: continue
        if (now - exp).total_seconds() < a.grace_minutes * 60: continue
        last = ((j.get("state") or {}).get("lastRunAtMs") or 0) / 1000.0
        if last and last >= exp.timestamp() - 300:
            continue  # 该档已经跑过（容差 5 分钟）
        picked.append((exp, name, j["id"]))

    seenf = os.path.join(W, "state/work/cron-catchup-seen.json")
    try:
        seen = json.load(open(seenf, encoding="utf-8"))
    except Exception:
        seen = {}
    nowts = now.timestamp()
    picked2 = []
    for e, n, jid in picked:
        if nowts - float(seen.get(jid, 0)) < 6 * 3600:
            skipped.append((n, "6 小时内已补跑过")); continue
        picked2.append((e, n, jid))
    picked = picked2
    picked.sort()
    if len(picked) > a.max:
        for _, n, _ in picked[a.max:]: skipped.append((n, "超过本次上限"))
        picked = picked[:a.max]
    say("候选 %d 个，跳过 %d 个" % (len(picked), len(skipped)))
    for e, n, _ in picked: say("  → 补跑 %s（应跑 %s）" % (n, e.strftime("%m-%d %H:%M")))
    if a.dry_run or not picked:
        say("=== catchup end (no run) ===")
        return 0

    ok, fail = [], []
    for _, n, jid in picked:
        say("run %s (%s)" % (n, jid))
        rc, out = sh(["openclaw", "cron", "run", jid], 300)
        (ok if rc == 0 else fail).append(n)
        seen[jid] = nowts
        try:
            json.dump(seen, open(seenf, "w", encoding="utf-8"))
        except Exception:
            pass
        say("  rc=%d" % rc)
    msg = "【漏档补跑】补跑 %d 个%s；跳过 %d 个" % (len(ok), ("：" + "、".join(ok)) if ok else "", len(skipped))
    if fail: msg += "；失败：" + "、".join(fail)
    say(msg)
    sh(["bash", os.path.join(W, "tools/notify.sh"), msg], 60)
    say("=== catchup end ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
