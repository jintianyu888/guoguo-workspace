#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""day-plan.py —— 每日三次时段排班（08:40 定全天 / 13:10 定下午+夜 / 18:20 定夜间）
读 state/tasks/tasks.db，按优先级与峰谷时段把未结任务排进四个时间块。
产出: state/work/day-plan.md（人看）+ state/work/day-plan.json（机器/日报复用）
用法: day-plan.py [--slot morning|noon|evening] [--quiet]
"""
import argparse, json, os, sqlite3, sys, datetime as dt

WS = "/home/j/.openclaw/workspace"
DB = os.path.join(WS, "state/tasks/tasks.db")
OUTD = os.path.join(WS, "state/work")
# 峰谷：(开始,结束) 高峰=只做零成本/入队；其余为半价窗可干重活
PEAK = [(9, 12), (14, 18)]
BLOCKS = [
    ("上午 09:00-12:00 高峰", 9, 12, "零成本活：本机脚本/自检/告警日清/台账核对，重活只入队"),
    ("午间 12:00-14:00 半价", 12, 14, "主攻重活（今天最能出成果的一段）"),
    ("下午 14:00-18:00 高峰", 14, 18, "零成本活 + 排队；除主公紧急/打印组外不动重活"),
    ("夜间 18:20 后半价", 18, 24, "批量重活：评审、脚本落地、助手改造"),
]

def q(sql, args=()):
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, args).fetchall()]
    finally:
        con.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", default="auto", choices=["auto", "morning", "noon", "evening"])
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    now = dt.datetime.now()
    hour = now.hour
    slot = a.slot if a.slot != "auto" else ("morning" if hour < 12 else ("noon" if hour < 18 else "evening"))
    today = now.strftime("%Y-%m-%d")

    try:
        rows = q("select no,title,status,prio,grp from tasks where status in ('pending','open','in_progress') and coalesce(blocked,0)=0 and coalesce(who,'agent')!='owner' and (select max(ts) from events e where e.no=tasks.no and coalesce(e.actor,'')!='migrate' and e.field not in ('import','who')) >= date('now','-21 day') order by (prio is null), prio, no")
    except Exception:
        rows = q("select no,title,status,prio,grp from tasks where status in ('pending','open','in_progress') order by (prio is null), prio, no")
    done_today = [r["no"] for r in q("select distinct no from events where ts like ? and field='status' and new='done'", (today + "%",))]
    closed_total = len(done_today)

    # 简单分配：按 prio 顺序，午间 2 项、夜间 3 项、高峰段各 1 项“零成本核查”
    pool = [r for r in rows]
    def take(n):
        out = []
        while pool and len(out) < n:
            out.append(pool.pop(0))
        return out

    assign = {}
    assign["上午 09:00-12:00 高峰"] = take(1) if hour < 12 else []
    assign["午间 12:00-14:00 半价"] = take(2) if hour < 14 else []
    assign["下午 14:00-18:00 高峰"] = take(1) if hour < 18 else []
    assign["夜间 18:20 后半价"] = take(3)

    lines = ["# 今日排班 %s（%s 生成）" % (today, now.strftime("%H:%M")), ""]
    lines.append("今日已关闭 %d 项｜未结 %d 项" % (closed_total, len(rows)))
    lines.append("")
    js = {"date": today, "generated": now.isoformat(timespec="seconds"), "slot": slot,
          "closed_today": closed_total, "open_total": len(rows), "blocks": []}
    for name, h0, h1, hint in BLOCKS:
        items = assign.get(name, [])
        if hour >= h1 and h1 < 24:
            mark = "（已过）"
        else:
            mark = ""
        lines.append("## %s %s" % (name, mark))
        lines.append("- 定位：%s" % hint)
        if items:
            for it in items:
                prio = it["prio"] if it["prio"] is not None else "-"
                lines.append("- 任务 #%s [p%s] %s" % (it["no"], prio, it["title"]))
        else:
            lines.append("- 无排定任务（处理临时事项/保持巡检）")
        lines.append("")
        js["blocks"].append({"name": name, "hint": hint, "passed": hour >= h1 and h1 < 24,
                             "tasks": [{"no": it["no"], "title": it["title"], "prio": it["prio"]} for it in items]})
    if rows[len(rows) - len(pool):]:
        pass
    # 晚间班次追加“明日预告”，让主公晚上就知道明天的计划
    if slot == "evening":
        lines.append("## 明日预告（%s）" % (now + dt.timedelta(days=1)).strftime("%m-%d"))
        lines.append("- 09:00-12:00 高峰：零成本活 + 抢购/巡检；重活只入队")
        lines.append("- 12:00-14:00 半价：主攻 %s" % ("、".join("#%s" % t["no"] for t in pool[:2]) if pool else "按早班重排"))
        lines.append("- 18:20 后：批量 %s" % ("、".join("#%s" % t["no"] for t in pool[2:5]) if len(pool) > 2 else "视当日进度"))
        lines.append("")
        js["tomorrow_preview"] = [{"no": t["no"], "title": t["title"]} for t in pool[:5]]

    rest = pool
    if rest:
        lines.append("## 排队（今晚排不上的）")
        for it in rest[:8]:
            lines.append("- #%s %s" % (it["no"], it["title"]))
        lines.append("")

    os.makedirs(OUTD, exist_ok=True)
    md = os.path.join(OUTD, "day-plan.md")
    with open(md + ".tmp", "w") as f:
        f.write("\n".join(lines) + "\n"); f.flush(); os.fsync(f.fileno())
    os.replace(md + ".tmp", md)
    js_path = os.path.join(OUTD, "day-plan.json")
    with open(js_path + ".tmp", "w") as f:
        json.dump(js, f, ensure_ascii=False, indent=1); f.flush(); os.fsync(f.fileno())
    os.replace(js_path + ".tmp", js_path)

    if not a.quiet:
        head = {12: "08:40 全天排班", 18: "13:10 下午+夜间排班", 24: "18:20 夜间排班"}
        title = "📋 今日排班（%s）" % now.strftime("%H:%M")
        print(title)
        print("今日已关闭 %d 项｜未结 %d 项" % (closed_total, len(rows)))
        for b in js["blocks"]:
            if b["passed"]: continue
            if not b["tasks"]: continue
            print("▸ %s" % b["name"])
            for t in b["tasks"]:
                print("  · #%s [p%s] %s" % (t["no"], t["prio"] if t["prio"] is not None else "-", t["title"][:44]))
        print("详情 state/work/day-plan.md")
    return 0

if __name__ == "__main__":
    sys.exit(main())
