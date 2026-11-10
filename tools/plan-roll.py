#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""plan-roll.py - miss rolling + escalation (dual-review rule, 2026-10-28)

--snapshot : parse today's day-plan.md, save planned task numbers to plan-hist/YYYY-MM-DD.json
--report   : compare yesterday's snapshot against tasks.db, classify misses, escalate after 2 misses
Exit: 0 ok; 4 escalation present (so caller can force-report)
"""
import json, os, re, sqlite3, sys, datetime as dt

WS = "/home/j/.openclaw/workspace"
DB = os.path.join(WS, "state/tasks/tasks.db")
WORK = os.path.join(WS, "state/work")
HIST = os.path.join(WORK, "plan-hist")
ROLL = os.path.join(WORK, "plan-roll.json")

def conn():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def load_roll():
    try:
        return json.load(open(ROLL))
    except Exception:
        return {"misses": {}, "updated": None}

def save_roll(d):
    d["updated"] = dt.datetime.now().isoformat(timespec="seconds")
    with open(ROLL + ".tmp", "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=1); f.flush(); os.fsync(f.fileno())
    os.replace(ROLL + ".tmp", ROLL)

def snapshot():
    os.makedirs(HIST, exist_ok=True)
    md = os.path.join(WORK, "day-plan.md")
    if not os.path.exists(md):
        print("无 day-plan.md，跳过快照"); return 1
    txt = open(md, encoding="utf-8").read()
    nos = []
    for m in re.finditer(r"#(\d+)\s*\[p", txt):
        n = int(m.group(1))
        if n not in nos: nos.append(n)
    today = dt.date.today().isoformat()
    fp0 = os.path.join(HIST, today + ".json")
    prev = []
    if os.path.exists(fp0):
        try: prev = json.load(open(fp0)).get("planned", [])
        except Exception: prev = []
    for n in prev:                      # 并集，绝不因重写而缩小分母
        if n not in nos: nos.append(n)
    out = {"date": today, "planned": nos, "snapshot_at": dt.datetime.now().isoformat(timespec="seconds")}
    fp = os.path.join(HIST, today + ".json")
    with open(fp + ".tmp", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1); f.flush(); os.fsync(f.fileno())
    os.replace(fp + ".tmp", fp)
    print("已快照今日计划 %d 项 -> %s" % (len(nos), fp))
    return 0

def report(days_back=1, quiet=False):
    c = conn(); roll = load_roll()
    now = dt.datetime.now()
    target = (now.date() - dt.timedelta(days=days_back))
    fp = os.path.join(HIST, target.isoformat() + ".json")
    if not os.path.exists(fp):
        if not quiet: print("无 %s 的计划快照，跳过未兑现核对" % target)
        return 0
    audited = roll.get("audited") or []
    if target.isoformat() in audited and "--reaudit" not in sys.argv:
        if not quiet: print("%s 已核对过，跳过（重复跑不重复计数）" % target)
        return 0
    planned = json.load(open(fp)).get("planned", [])
    if not planned:
        if not quiet: print("%s 无排班项" % target)
        return 0
    rows = {}
    for r in c.execute("select no,title,status,blocked,blocked_reason from tasks"):
        rows[int(r["no"])] = dict(r)
    fu, miss_self, miss_ext, delay = [], [], [], []
    for n in planned:
        t = rows.get(n)
        if t is None:
            miss_self.append((n, "任务已不存在")); continue
        if t["status"] == "done":
            delay.append((n, t["title"]))
        elif int(t.get("blocked") or 0) == 1:
            miss_ext.append((n, t["title"], t.get("blocked_reason") or "外部阻塞未填原因"))
        else:
            miss_self.append((n, t["title"]))
    esc = []
    ms = roll.setdefault("misses", {})
    for n, _t in miss_self + [(a, b) for a, b, _c in miss_ext]:
        rec = ms.get(str(n)) or {"count": 0, "dates": []}
        dates = rec.get("dates") or []
        if target.isoformat() in dates:      # 同一天只算一次，重跑不重复计数
            if int(rec.get("count", 0)) == 2: esc.append((n, 2))
            continue
        rec["count"] = int(rec.get("count", 0)) + 1
        rec["dates"] = (dates + [target.isoformat()])[-30:]
        rec["last"] = target.isoformat()
        ms[str(n)] = rec
        if rec["count"] == 2: esc.append((n, 2))   # 只在首次跃迁时催，不每天刷屏
    for n in [x for x, _ in delay]:
        if str(n) in ms: ms[str(n)]["count"] = 0
    roll["audited"] = (roll.get("audited") or []) + [target.isoformat()]
    roll["audited"] = roll["audited"][-60:]
    save_roll(roll)

    n_plan = len(planned)
    rate = len(delay) / float(n_plan) * 100.0 if n_plan else 0.0
    L = []
    L.append("兑现率 %.0f%%（%d/%d）｜延期完成 %d｜自身未做 %d｜外部阻塞 %d" % (rate, len(delay), n_plan, len(delay), len(miss_self), len(miss_ext)))
    if miss_ext:
        L.append("外部阻塞（不计我的账）：")
        for n, t, why in miss_ext: L.append("  - #%s %s｜%s" % (n, t[:36], why))
    if miss_self:
        L.append("自身未做（要认账）：")
        for n, t in miss_self: L.append("  - #%s %s" % (n, (t if isinstance(t, str) else "")[:40]))
    if esc:
        L.append("连续未兑现 %d 项 -> 需裁决（拆分/砍掉/改优先级）：" % len(esc))
        for n, k in esc: L.append("  - #%s 连续 %d 次未兑现" % (n, k))
    if not quiet: print("\n".join(L))
    return 4 if esc else 0

if __name__ == "__main__":
    a = sys.argv[1:]
    if "--snapshot" in a: sys.exit(snapshot())
    if "--report" in a:
        db = 1
        for i, x in enumerate(a):
            if x == "--days": db = int(a[i + 1])
        sys.exit(report(db, quiet=("--quiet" in a)))
    print("用法: plan-roll.py --snapshot | --report [--days N] [--quiet]")
    sys.exit(2)
