#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管家周记分（主公 2026-11-07 令：所有维护/系统运行管家参与打分，每周出报告）

基础 100，全部来自落盘数据：
  任务  ：due_plan 落在本周期的台账项；提前≥24h +5 / ≥2h +3 / ≥15min +1；逾期≤2h -2 / ≤24h -5 / >24h -10；
          逾期仍未完成且无原因 -5；任务合计封顶 +40 / 下限 -30
  cron  ：本周 cron_run_receipts 成功率，扣分 =(1-成功率)×20
  自审  ：应每天一份，缺一天 -2（main 认 summary/acceptance/sheet 日报）
  人工  ：state/plan/adjustments-YYYYMMDD.json 中带 agent 字段的项
用法：python3 tools/butler-score.py [--json]   → state/plan/butler-score-<年>-W<周>.md
"""
import sqlite3, json, os, sys, datetime, glob

WS = "/home/j/.openclaw/workspace"
OC = "/home/j/.openclaw"
NAMES = {"main": "果果", "maint": "维护管家", "backup": "备份管家", "model": "模型管家",
         "work": "干活管家", "sheet-music": "Hermess", "print": "格格", "news": "资讯管家"}
TARGET = ["main", "maint", "backup", "model", "work", "sheet-music", "print", "news"]
DAILY = {"main", "maint", "backup", "model", "work", "sheet-music"}

def ws_of(a):
    try:
        d = json.load(open(OC + "/openclaw.json", encoding="utf-8"))
        e = d.get("agents", {}).get("entries", {}).get(a) or {}
        return e.get("workspace") or "%s/workspace-%s" % (OC, a)
    except Exception:
        return ""

def parse(s):
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s, f)
        except Exception:
            pass
    return None

def main():
    today = datetime.date.today()
    mom = today - datetime.timedelta(days=today.weekday())
    sun = mom + datetime.timedelta(days=6)
    start = datetime.datetime.combine(mom, datetime.time(0, 0))
    end = datetime.datetime.combine(sun, datetime.time(23, 59))
    sc = {a: {"task": 0, "cron": 0, "self": 0, "manual": 0, "detail": [], "n": 0,
              "succ": 0, "fail": 0, "days": 0} for a in TARGET}

    c = sqlite3.connect(WS + "/state/tasks/tasks.db")
    c.row_factory = sqlite3.Row
    for r in c.execute("select no,title,status,agent,due_plan,updated,slip_reason from tasks where due_plan is not null"):
        a = (r["agent"] or "main").strip() or "main"
        if a not in sc:
            continue
        due = parse(r["due_plan"] or "")
        if not due or not (start <= due <= end):
            continue
        st = (r["status"] or "").lower()
        s = None
        if st == "done":
            fin = parse((r["updated"] or "")[:16]) or due
            d = (due - fin).total_seconds() / 60.0
            if d >= 1440: s = 5
            elif d >= 120: s = 3
            elif d >= 15: s = 1
            elif d >= -15: s = 0
            elif d >= -120: s = -2
            elif d >= -1440: s = -5
            else: s = -10
            sc[a]["n"] += 1
        elif datetime.datetime.now() > due:
            s = 0 if r["slip_reason"] else -5
        if s is None:
            continue
        sc[a]["task"] += s
        sc[a]["detail"].append("#%s %s %+d" % (r["no"], (r["title"] or "")[:14], s))
    for a in sc:
        sc[a]["task"] = max(-30, min(40, sc[a]["task"]))

    cc = sqlite3.connect(OC + "/state/openclaw.sqlite")
    ms = int(start.timestamp() * 1000)
    for aid, st, n in cc.execute("select agent_id,status,count(*) from cron_run_receipts where started_at_ms>=? group by agent_id,status", (ms,)):
        a = aid or "main"
        if a not in sc:
            continue
        if (st or "").lower() in ("ok", "success", "done"):
            sc[a]["succ"] += n
        else:
            sc[a]["fail"] += n
    for a, v in sc.items():
        runs = v["succ"] + v["fail"]
        v["runs"] = runs
        v["cron"] = 0 if runs == 0 else -round(v["fail"] / runs * 20, 1)

    for a, v in sc.items():
        if a not in DAILY:
            continue
        w = ws_of(a)
        got = 0
        for i in range(7):
            d = mom + datetime.timedelta(days=i)
            if d > today:
                break
            k1, k2 = d.strftime("%Y%m%d"), d.strftime("%Y-%m-%d")
            pats = ["%s/state/self-review/%s*.md" % (w, k1), "%s/state/self-review/%s*.md" % (w, k2),
                    "%s/state/self-review/%s-%s*.md" % (WS, a, k2), "%s/state/self-review/%s-%s*.md" % (WS, a, k1)]
            if a == "main":
                pats += ["%s/state/self-review/summary-%s*.md" % (WS, k1),
                         "%s/state/self-review/acceptance-%s*.md" % (WS, k1),
                         "%s/state/self-review/sheet-%s*.md" % (WS, k1)]
            if any(glob.glob(p) for p in pats):
                got += 1
        v["days"] = got
        expect = min(7, today.isoweekday())
        v["self"] = -2 * max(0, expect - got)

    for f in sorted(glob.glob(WS + "/state/plan/adjustments-*.json")):
        ds = f.rsplit("-", 1)[-1].split(".")[0]
        try:
            dd = datetime.datetime.strptime(ds, "%Y%m%d").date()
        except Exception:
            continue
        if not (mom <= dd <= sun):
            continue
        try:
            items = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        for it in items:
            a = it.get("agent")
            if a in sc:
                sc[a]["manual"] += int(it.get("delta", 0))
                sc[a]["detail"].append("人工 %s %+d" % (str(it.get("why", ""))[:16], int(it.get("delta", 0))))

    y, wk, _ = today.isocalendar()
    rank = sorted(sc.items(), key=lambda kv: -(100 + kv[1]["task"] + kv[1]["cron"] + kv[1]["self"] + kv[1]["manual"]))
    lines = ["# 管家周记分 %s ~ %s（第%d周）" % (mom, sun, wk), ""]
    for a, v in rank:
        total = 100 + v["task"] + v["cron"] + v["self"] + v["manual"]
        rate = ("%.0f%%" % (100.0 * v["succ"] / v["runs"])) if v["runs"] else "无 cron 任务"
        lines.append("## %s（%s）：**%.0f 分**" % (NAMES.get(a, a), a, total))
        lines.append("- 任务 %+d（%d 条）｜cron %+.1f（%d 次，成功率 %s）｜自审 %+d（%d 天）｜人工 %+d" % (
            v["task"], v["n"], v["cron"], v["runs"], rate, v["self"], v["days"], v["manual"]))
        if v["detail"]:
            lines.append("- 明细：" + "；".join(v["detail"][:6]))
        lines.append("")
    txt = "\n".join(lines)
    os.makedirs(WS + "/state/plan", exist_ok=True)
    out = "%s/state/plan/butler-score-%d-W%02d.md" % (WS, y, wk)
    open(out, "w", encoding="utf-8").write(txt)
    if "--json" in sys.argv:
        print(json.dumps({a: round(100 + v["task"] + v["cron"] + v["self"] + v["manual"]) for a, v in sc.items()}, ensure_ascii=False))
    else:
        print(txt)
        print("→ " + out)

if __name__ == "__main__":
    main()
