#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""plan-report.py v1.1 - monthly/weekly plan + progress + honest ETA (dual-review revised)
Fixes: blocked excluded; ETA = median weekly closes /5 with range; inflow ratio; capacity calibration; prio aging.
"""
import argparse, json, os, sqlite3, statistics, sys, datetime as dt
from collections import defaultdict

WS = "/home/j/.openclaw/workspace"
DB = os.path.join(WS, "state/tasks/tasks.db")
OUTD = os.path.join(WS, "state/work")
OPEN_ST = ("pending", "open", "in_progress", "paused")

def q(sql, args=()):
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    try: return [dict(r) for r in con.execute(sql, args).fetchall()]
    finally: con.close()

def tp(v):
    try: return int(v)
    except Exception: return 99

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="all", choices=["month", "week", "day", "all"])
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    now = dt.datetime.now()

    tasks = q("select no,title,status,prio,grp,blocked,blocked_reason,verify,who from tasks")
    def is_blocked(t): return int(t.get("blocked") or 0) == 1
    open_all = [t for t in tasks if (t["status"] or "") in OPEN_ST]
    blocked = [t for t in open_all if is_blocked(t)]
    open_items = [t for t in open_all if not is_blocked(t)]
    owner_items = [t for t in open_items if (t.get('who') or 'agent') == 'owner']
    open_items = [t for t in open_items if (t.get('who') or 'agent') != 'owner']   # 我自己的活
    done = [t for t in tasks if t["status"] == "done"]
    denom = len(done) + len(open_items)
    pct = (len(done) / denom * 100.0) if denom else 0.0
    verified = len([t for t in done if t.get("verify")])

    weeks = 8
    since = (now - dt.timedelta(weeks=weeks)).strftime("%Y-%m-%d")
    closes = q("select ts from events where field='status' and new='done' and ts >= ?", (since,))
    creates = q("select ts from events where field='create' and ts >= ?", (since,))
    def per_week(rows):
        bucket = defaultdict(int)
        for r in rows:
            try: d0 = dt.datetime.strptime(r["ts"][:10], "%Y-%m-%d")
            except Exception: continue
            bucket[d0.isocalendar()[1]] += 1
        return [bucket[k] for k in sorted(bucket)]
    cw, nw = per_week(closes), per_week(creates)
    med_close_wk = statistics.median(cw) if cw else 0
    med_new_wk = statistics.median(nw) if nw else 0
    per_day = med_close_wk / 5.0 if med_close_wk else 0.0
    per_day_low = (min(cw) / 5.0) if cw else 0.0
    per_day_high = (max(cw) / 5.0) if cw else 0.0
    if med_close_wk:
        inflow_ratio = med_new_wk / med_close_wk
    else:
        inflow_ratio = None if not med_new_wk else float("inf")
    backlog = len(open_items)
    eta_mid = backlog / per_day if per_day > 0 else None
    eta_lo = backlog / per_day_high if per_day_high > 0 else None
    eta_hi = backlog / per_day_low if per_day_low > 0 else None
    def dstr(x): return (now + dt.timedelta(days=x)).strftime("%Y-%m-%d") if x else "-"
    converging = (inflow_ratio is not None) and (inflow_ratio < 1.0)

    last_touch = {}
    for r in q("select no, max(ts) as ts from events group by no"):
        last_touch[r["no"]] = r["ts"]
    def idle_days(t):
        ts = last_touch.get(t["no"])
        if not ts: return 60
        try: return max(0, (now - dt.datetime.strptime(ts[:10], "%Y-%m-%d")).days)
        except Exception: return 60
    def score(t): return tp(t["prio"]) * 10 - min(idle_days(t), 60) / 6.0
    pool = sorted(open_items, key=lambda t: (score(t), tp(t["no"])))
    cap = max(3, min(8, int(max(per_day, 0.4) * 5 * 0.9)))

    by_grp = defaultdict(lambda: {"done": 0, "open": 0, "blocked": 0})
    for t in tasks:
        g = t["grp"] or "未分类"
        if t["status"] == "done": by_grp[g]["done"] += 1
        elif (t["status"] or "") in OPEN_ST:
            by_grp[g]["blocked" if is_blocked(t) else "open"] += 1

    prog = {"generated": now.isoformat(timespec="seconds"), "total": len(tasks), "done": len(done),
            "open": len(open_items), "blocked": len(blocked), "pct": round(pct, 1),
            "median_close_per_week": med_close_wk, "median_new_per_week": med_new_wk,
            "inflow_ratio": (None if inflow_ratio is None else ("inf" if inflow_ratio == float("inf") else round(inflow_ratio, 2))),
            "eta_days_mid": round(eta_mid, 1) if eta_mid else None,
            "eta_days_range": [round(eta_lo, 1), round(eta_hi, 1)] if (eta_lo and eta_hi) else None,
            "converging": converging, "weekly_capacity_plan": cap,
            "by_group": {k: v for k, v in sorted(by_grp.items())}}
    os.makedirs(OUTD, exist_ok=True)
    pth = os.path.join(OUTD, "plan-progress.json")
    with open(pth + ".tmp", "w") as f:
        json.dump(prog, f, ensure_ascii=False, indent=1); f.flush(); os.fsync(f.fileno())
    os.replace(pth + ".tmp", pth)

    head = []
    head.append("① 完成率 %.1f%%（%d/%d；其中带 verify 的 %d 项）" % (pct, len(done), denom, verified))
    head.append("② 周流入/关闭比 %s（新增 %.1f / 关闭 %.1f 项每周）%s" % (
        ("-" if inflow_ratio is None else ("inf 只进不出" if inflow_ratio == float("inf") else "%.2f" % inflow_ratio)),
        med_new_wk, med_close_wk, "" if converging else " → 不收敛：新增≥关闭，清空无期限"))
    head.append("③ ETA 区间 %s（中值 %.0f 天｜日均关闭 %.2f 项｜阻塞 %d 项已排除）" % (
        ("%s ~ %s" % (dstr(eta_lo), dstr(eta_hi))) if (eta_lo and eta_hi) else "无法估算",
        eta_mid or 0, per_day, len(blocked)))

    if a.level in ("month", "all"):
        mstart = now.replace(day=1)
        mend = (mstart + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
        n_month = min(10, max(cap, 6))
        L = ["# 月计划 %s（%s ~ %s）" % (mstart.strftime("%Y-%m"), mstart.date(), mend.date()), "", "## 三个头条数字", ""]
        L += ["- " + h for h in head] + [""]
        L.append("## 本月目标（容量校准 %d 项）" % n_month)
        for i, t in enumerate(pool[:n_month], 1):
            L.append("%d. #%s [p%s] %s%s" % (i, t["no"], t["prio"] if t["prio"] is not None else "-", t["title"],
                                            "（闲置 %d 天）" % idle_days(t) if idle_days(t) > 14 else ""))
        L.append("")
        if blocked:
            L.append("## 阻塞项（不计入完成率与 ETA）")
            for t in blocked:
                L.append("- #%s %s｜原因：%s" % (t["no"], t["title"][:40], (t.get("blocked_reason") or "未填")))
            L.append("")
        L.append("## 分组完成度")
        for g, v in sorted(by_grp.items(), key=lambda kv: -(kv[1]["open"] + kv[1]["blocked"])):
            tot = v["done"] + v["open"] + v["blocked"]
            L.append("- %s：%d/%d（在办 %d，阻塞 %d）" % (g, v["done"], tot, v["open"], v["blocked"]))
        L.append("")
        with open(os.path.join(OUTD, "plan-month.md"), "w") as f: f.write("\n".join(L) + "\n")

    if a.level in ("week", "all"):
        wstart = now - dt.timedelta(days=now.weekday())
        wend = wstart + dt.timedelta(days=6)
        L = ["# 周计划 %s（%s ~ %s）" % (now.strftime("%G-W%V"), wstart.date(), wend.date()), "", "## 三个头条数字", ""]
        L += ["- " + h for h in head] + [""]
        L.append("## 本周目标（按产能校准为 %d 项）" % cap)
        for i, t in enumerate(pool[:cap], 1):
            L.append("%d. #%s [p%s] %s" % (i, t["no"], t["prio"] if t["prio"] is not None else "-", t["title"]))
            if t.get("verify"):
                L.append("   - 验收命令：%s" % t["verify"])
        L.append("")
        L.append("## 兜底：进度落后时先砍这些")
        for t in pool[cap:cap + 4]:
            L.append("- #%s %s" % (t["no"], t["title"][:50]))
        L.append("")
        with open(os.path.join(OUTD, "plan-week.md"), "w") as f: f.write("\n".join(L) + "\n")

    if True:
        L = ["# 主公待办（需要你本人动手，我不代做）", ""]
        if owner_items:
            for i, t in enumerate(sorted(owner_items, key=lambda x: tp(x["prio"])), 1):
                L.append("%d. #%s [p%s] %s" % (i, t["no"], t["prio"] if t["prio"] is not None else "-", t["title"]))
        else:
            L.append("无")
        L.append("")
        L.append("共 %d 项；每日只提 1 项，其余不催。" % len(owner_items))
        with open(os.path.join(OUTD, "owner-todo.md"), "w") as f:
            f.write("\n".join(L) + "\n")
    if not a.quiet:
        print("总体进度三数字：")
        for h in head: print("  " + h)
        print("周计划容量 %d 项｜我的未结 %d（阻塞 %d）｜主公待办 %d 项｜排序前5：%s" % (cap, len(open_items), len(blocked), len(owner_items), "、".join("#%s" % t["no"] for t in pool[:5])))
        print("详情：state/work/plan-month.md、plan-week.md、plan-progress.json")
    return 0

if __name__ == "__main__":
    sys.exit(main())
