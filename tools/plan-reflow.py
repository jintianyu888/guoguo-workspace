#!/usr/bin/env python3
"""plan-reflow.py —— 提前完成后自动前移后续计划（2026-11-07 主公令）
规则：
  · 只排「未完成 + 有 eta_min + 未固定时间」的任务，顺序按原计划时间
  · 起点 = 现在+5分钟（向上对齐 5 分钟），工作窗口 08:30–22:30，跳过红区 01:00–02:30 / 04:00–06:05 / 07:45–08:15
  · 固定时间（wait_user=1 或 pin_time=1）保持原计划，并把它占用的时段当作硬约束
  · 只提前不推后：新时间若比原计划更晚，则保留原计划
用法：plan-reflow.py [--dry-run]
"""
import argparse, datetime as dt, os, sqlite3, sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(W, "state/tasks/tasks.db")
FMT = "%Y-%m-%d %H:%M"
OPEN = ("open", "pending", "in_progress")
WIN_S, WIN_E = dt.time(8, 30), dt.time(22, 30)
RED = [(dt.time(1, 0), dt.time(2, 30)), (dt.time(4, 0), dt.time(6, 5)), (dt.time(7, 45), dt.time(8, 15))]

def ceil5(t):
    t = t.replace(second=0, microsecond=0)
    return t + dt.timedelta(minutes=(-t.minute) % 5)

def normalize(t):
    """把 t 推到合法工作时刻"""
    for _ in range(8):
        if t.time() < WIN_S:
            t = dt.datetime.combine(t.date(), WIN_S)
        elif t.time() >= WIN_E:
            t = dt.datetime.combine(t.date() + dt.timedelta(days=1), WIN_S)
        hit = None
        for a, b in RED:
            if a <= t.time() < b:
                hit = b; break
        if hit:
            t = dt.datetime.combine(t.date(), hit); continue
        break
    return t

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    c = sqlite3.connect(DB, timeout=10); c.row_factory = sqlite3.Row
    cols = [r[1] for r in c.execute("pragma table_info(tasks)")]
    if "pin_time" not in cols:
        c.execute("alter table tasks add column pin_time integer default 0"); c.commit()

    rows = [dict(r) for r in c.execute(
        "select no,title,due_plan,eta_min,wait_user,pin_time,prio from tasks where status in ('open','pending','in_progress')")]
    if not rows:
        print("无在办任务"); return 0

    now = dt.datetime.now()
    cursor = normalize(ceil5(now + dt.timedelta(minutes=int(__import__("os").environ.get("REFLOW_GAP_MIN", "1")))))
    def key(r):
        try: return dt.datetime.strptime((r["due_plan"] or "")[:16], FMT)
        except Exception: return dt.datetime(2099, 1, 1)
    rows.sort(key=key)

    changes = []
    for r in rows:
        pinned = bool(r["wait_user"]) or bool(r["pin_time"])
        eta = int(r["eta_min"] or 30)
        if pinned:
            try:
                end = dt.datetime.strptime((r["due_plan"] or "")[:16], FMT) + dt.timedelta(minutes=eta)
                if end > cursor: cursor = normalize(end)
            except Exception: pass
            continue
        start = cursor
        old = (r["due_plan"] or "")[:16]
        if old:
            try:
                if key(r) < start: start = key(r)   # 只提前不推后
            except Exception: pass
        new = start.strftime(FMT)
        if new != old:
            changes.append((r["no"], r["title"][:26], old or "-", new, eta))
            if not a.dry_run:
                c.execute("update tasks set due_plan=?, updated=? where no=?", (new, now.strftime(FMT), r["no"]))
        cursor = normalize(start + dt.timedelta(minutes=eta))
    if not a.dry_run and changes:
        c.commit()
    for no, t, o, n, e in changes:
        print("#%-4s %-28s %s -> %s (约%dm)" % (no, t, o, n, e))
    print(("DRY-RUN " if a.dry_run else "") + "前移 %d 项" % len(changes))
    return 0

if __name__ == "__main__":
    sys.exit(main())
