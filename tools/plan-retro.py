#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""plan-retro.py - weekly/monthly retrospective that forces split/cut (dual-review rule 2026-10-28)

Weekly: coverage of planned tasks, leftover list; >3 leftover => exit 5 and demand split/cut/escalate.
Monthly: month plan targets vs done, plus blocked/slipped reasons.
Writes state/reports/retro-<period>.md
"""
import json, os, re, sqlite3, sys, datetime as dt

WS = "/home/j/.openclaw/workspace"
DB = os.path.join(WS, "state/tasks/tasks.db")
WORK = os.path.join(WS, "state/work")
HIST = os.path.join(WORK, "plan-hist")
REP = os.path.join(WS, "state/reports")

def conn():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def month_targets():
    p = os.path.join(WORK, "plan-month.md")
    if not os.path.exists(p): return []
    return [int(x) for x in re.findall(r"^\d+\.\s*#(\d+)", open(p, encoding="utf-8").read(), re.M)]

def collect(days):
    since = dt.date.today() - dt.timedelta(days=days - 1)
    planned = {}
    if os.path.isdir(HIST):
        for fn in sorted(os.listdir(HIST)):
            if not fn.endswith(".json"): continue
            try:
                d = dt.date.fromisoformat(fn[:-5])
            except Exception:
                continue
            if d < since or d >= dt.date.today(): continue   # 今天及以后还没到期，不算欠账
            for n in json.load(open(os.path.join(HIST, fn))).get("planned", []):
                planned.setdefault(int(n), 0)
                planned[int(n)] += 1
    return planned

def main():
    weekly = "--weekly" in sys.argv
    days = 7 if weekly else 30
    c = conn()
    rows = {int(r["no"]): dict(r) for r in c.execute("select no,title,status,blocked,blocked_reason,prio from tasks")}
    planned = collect(days)
    done = [n for n in planned if rows.get(n, {}).get("status") == "done"]
    left = [n for n in planned if rows.get(n, {}).get("status") != "done"]
    left_ext = [n for n in left if int(rows.get(n, {}).get("blocked") or 0) == 1]
    left_self = [n for n in left if n not in left_ext]
    try:
        waivers = set(int(x) for x in json.load(open(os.path.join(WORK, "plan-waivers.json"))).get("nos", []))
    except Exception:
        waivers = set()
    left_self = [n for n in left_self if n not in waivers]
    cov = (len(done) / float(len(planned)) * 100.0) if planned else 0.0
    period = dt.date.today().strftime("%G-W%V") if weekly else dt.date.today().strftime("%Y-%m")
    latch = os.path.join(WORK, "plan-retro-latch.json")
    try:
        seen = json.load(open(latch)).get("periods", [])
    except Exception:
        seen = []
    if period in seen and "--force" not in sys.argv:
        print("%s 复盘本期已出过，跳过（要重出加 --force）" % period)
        return 0
    seen = (seen + [period])[-40:]
    with open(latch + ".tmp", "w") as f:
        json.dump({"periods": seen}, f); f.flush(); os.fsync(f.fileno())
    os.replace(latch + ".tmp", latch)
    L = ["# %s复盘 %s" % ("周" if weekly else "月", period), ""]
    L.append("- 排过班的项：%d｜已兑现：%d｜覆盖率 %.0f%%" % (len(planned), len(done), cov))
    L.append("- 未兑现 自身：%d｜外部阻塞：%d" % (len(left_self), len(left_ext)))
    mts = month_targets() if not weekly else []
    if mts:
        md = [n for n in mts if rows.get(n, {}).get("status") == "done"]
        L.append("- 本月目标进度：%d/%d" % (len(md), len(mts)))
        miss_m = [n for n in mts if n not in md]
        if miss_m: L.append("- 本月目标未达成：" + "、".join("#%d" % n for n in miss_m))
    if left_self:
        L.append("")
        L.append("## 必须处置（拆分/砍掉/升优先级，不许原样滚下期）")
        for n in left_self:
            t = rows.get(n, {})
            L.append("- #%d [p%s] %s" % (n, t.get("prio") if t.get("prio") is not None else "-", (t.get("title") or "")[:50]))
    if left_ext:
        L.append("")
        L.append("## 外部阻塞（等谁/等什么）")
        for n in left_ext:
            t = rows.get(n, {})
            L.append("- #%d %s｜%s" % (n, (t.get("title") or "")[:40], t.get("blocked_reason") or "未填原因"))
    os.makedirs(REP, exist_ok=True)
    p = os.path.join(REP, "retro-%s.md" % period)
    with open(p + ".tmp", "w") as f: f.write("\n".join(L) + "\n"); f.flush(); os.fsync(f.fileno())
    os.replace(p + ".tmp", p)
    print("\n".join(L))
    print("\n报告：%s" % p)
    if len(left_self) > 3:
        print("!! 未兑现自身项 %d > 3，按规则必须拆分或砍掉后才允许下期排班" % len(left_self))
        return 5
    return 0

if __name__ == "__main__":
    sys.exit(main())
