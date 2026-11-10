#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""plan-score.py —— 计划分：提前完成加分，逾期扣分（2026-11-07 主公令）

规则（基准分 10 分/条，按完成时刻与 due_plan 的差值加扣）
  提前 ≥ 24h   +5
  提前 ≥ 2h    +3
  提前 ≥ 15min +1
  准时 ±15min   0
  逾期 ≤ 2h    -2
  逾期 ≤ 24h   -5
  逾期 > 24h  -10（并标 STALE）
未完成：有原因 0；无原因 -5
人工调整项（返工/事故）从 state/plan/adjustments-YYYYMMDD.json 读，格式 [{"why":"…","delta":-5}]
用法：python3 tools/plan-score.py [YYYY-MM-DD]
"""
import sqlite3, datetime, json, os, sys
WS = "/home/j/.openclaw/workspace"
DB = WS + "/state/tasks/tasks.db"
PD = WS + "/state/plan"

def parse(s):
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try: return datetime.datetime.strptime(s, f)
        except Exception: pass
    return None

def main():
    day = datetime.date.today()
    if len(sys.argv) > 1 and sys.argv[1][:4].isdigit():
        day = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute("select no,title,status,due_plan,eta_min,slip_reason,updated from tasks where due_plan is not null")]
    lines, total, done_n, early_n, late_n = [], 0, 0, 0, 0
    for r in sorted(rows, key=lambda x: x["due_plan"]):
        due = parse(r["due_plan"] or "")
        if not due: continue
        st = (r["status"] or "").lower()
        title = (r["title"] or "")[:34]
        if st == "done":
            fin = parse((r["updated"] or "")[:16]) or due
            if fin.date() != day: continue
            d = (due - fin).total_seconds() / 60.0
            if d >= 1440: s, tag = 5, "提前≥24h"
            elif d >= 120: s, tag = 3, "提前≥2h"
            elif d >= 15: s, tag = 1, "提前"
            elif d >= -15: s, tag = 0, "准时"
            elif d >= -120: s, tag = -2, "逾期≤2h"
            elif d >= -1440: s, tag = -5, "逾期≤24h"
            else: s, tag = -10, "逾期>24h(STALE)"
            sc = 10 + s; total += sc; done_n += 1
            if s > 0: early_n += 1
            if s < 0: late_n += 1
            lines.append("  #%s %s｜%s %d 分（%s）" % (r["no"], title, tag, sc, (r["updated"] or "")[5:16]))
        else:
            if due.date() > day: continue
            over = (datetime.datetime.now() - due).total_seconds() / 3600.0
            if over <= 0: continue
            if r["slip_reason"]:
                lines.append("  #%s %s｜逾期未完成，有原因 0 分" % (r["no"], title))
            else:
                total -= 5; late_n += 1
                lines.append("  #%s %s｜逾期未完成且无原因 -5 分" % (r["no"], title))
    adjf = "%s/adjustments-%s.json" % (PD, day.strftime("%Y%m%d"))
    if os.path.exists(adjf):
        try:
            for a in json.load(open(adjf, encoding="utf-8")):
                total += int(a.get("delta", 0))
                lines.append("  人工调整：%s %+d 分" % (a.get("why", ""), int(a.get("delta", 0))))
        except Exception as e:
            lines.append("  调整项读取失败: %s" % e)
    out = ["## 计划分 %s" % day.isoformat(),
           "- 今日完成 %d 条（提前 %d / 逾期 %d），总分 **%d**" % (done_n, early_n, late_n, total)]
    out += lines
    txt = "\n".join(out)
    print(txt)
    os.makedirs(PD, exist_ok=True)
    open("%s/score-plan-%s.md" % (PD, day.strftime("%Y%m%d")), "w", encoding="utf-8").write(txt + "\n")

if __name__ == "__main__":
    main()
