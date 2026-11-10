#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""daily-briefing.py —— 早/中/晚三段式工作计划与完成度（零 token，cron 直跑）
用法: daily-briefing.py morning|noon|evening [--dry]
数据源: state/tasks/tasks.db + 各管家 state/self-review/*.md + cron_run_receipts
"""
import sqlite3, sys, os, json, time, datetime, re, subprocess

WS = "/home/j/.openclaw/workspace"
DB = os.path.join(WS, "state/tasks/tasks.db")
CDB = "/home/j/.openclaw/state/openclaw.sqlite"
BUTLERS = [("maint","维护管家"),("backup","备份管家"),("model","模型管家"),("work","干活管家"),("sheet-music","Hermess")]

import subprocess

def q(sql, args=()):
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    try: return c.execute(sql, args).fetchall()
    finally: c.close()

def today():
    return datetime.date.today().isoformat()

def plan_of_day(d):
    return q("select no,title,status,due_plan,eta_min,agent,who,slip_reason from tasks "
             "where due_plan like ? order by due_plan", (d+"%",))

def completed_on(d):
    return q("select no,title,agent from tasks where status='done' and updated like ?", (d+"%",))

def open_tasks():
    return q("select no,title,status,due_plan,agent from tasks where status not in ('done','cancelled','paused') order by due_plan is null, due_plan")

def cron_stats(hours=24):
    try:
        c = sqlite3.connect(CDB); c.row_factory = sqlite3.Row
        since = int((time.time()-hours*3600)*1000)
        rows = c.execute("select agent_id,status,count(*) n from cron_run_receipts where started_at_ms>=? group by agent_id,status",(since,)).fetchall()
        c.close()
    except Exception:
        return {}
    out = {}
    for r in rows:
        a = r["agent_id"] or "main"
        d = out.setdefault(a, {"ok":0,"bad":0})
        if r["status"] == "ok": d["ok"] += r["n"]
        else: d["bad"] += r["n"]
    return out

def review_receipt(agent):
    """用自审 cron 的当日回执判断「交没交」"""
    try:
        c = sqlite3.connect(CDB); c.row_factory = sqlite3.Row
        row = c.execute("select job_id,name from cron_jobs where name like ?", ("%自审%"+agent+"%",)).fetchone()
        if not row:
            row = c.execute("select job_id,name from cron_jobs where job_id in (select job_id from cron_jobs where name like '%自审%') and name like ?", ("%"+agent+"%",)).fetchone()
        if not row:
            c.close(); return None, None
        since = int((time.time()-36*3600)*1000)
        r = c.execute("select status,started_at_ms from cron_run_receipts where job_id=? and started_at_ms>=? order by started_at_ms desc limit 1", (row["job_id"], since)).fetchone()
        c.close()
        if not r: return "缺", None
        return ("已交" if r["status"]=="ok" else "失败"), r["started_at_ms"]
    except Exception:
        return None, None

def self_review(agent, d):
    cands = [os.path.join("/home/j/openclaw-workspaces", agent, "state/self-review"),
             os.path.join(WS, "state/self-review")]
    names = [d.replace("-","")+".md", d+".md"]
    for base in cands:
        for n in names:
            p = os.path.join(base, n)
            if os.path.exists(p):
                txt = open(p, encoding="utf-8", errors="ignore").read()
                return p, txt
    return None, ""

def plan_lines(txt, limit=3):
    """优先读机器可读 PLAN| 行，退回「明日计划」段落"""
    mk = [re.sub(r"^PLAN[|｜]\s*", "", l).strip() for l in txt.splitlines() if l.strip().startswith(("PLAN|","PLAN｜"))]
    if mk:
        return [x[:70] for x in mk if x][:limit]
    return _plan_lines_md(txt, limit)

def _plan_lines_md(txt, limit=3):
    """从自审里抓「明日计划/今日计划」行"""
    out = []
    grab = False
    for ln in txt.splitlines():
        s = ln.strip()
        if re.search(r"(明日|明天|次日).*(计划)|计划.*(明日|明天)", s):
            grab = True; continue
        if grab:
            if s.startswith("#") or re.match(r"^[一二三四五六]", s): break
            m = re.sub(r"^[-*·\d.、\)\s:：]+", "", s)
            if len(m) > 6: out.append(m[:60])
            if len(out) >= limit: break
    return out

def pct(done, total):
    return 0 if not total else int(round(done*100.0/total))

def build(slot):
    d = today()
    planned = plan_of_day(d)
    done_plan = [r for r in planned if r["status"] == "done"]
    done_any = completed_on(d)
    op = open_tasks()
    cs = cron_stats(24)
    L = []
    hdr = {"morning":"早间工作计划", "noon":"午间进度", "evening":"晚间复盘"}[slot]
    L.append("【%s · %s】" % (hdr, d))

    # 果果
    L.append("\n▍果果")
    # 周末清账（周六/周日显示；2026-11-07 主公令）
    wd = __import__("datetime").datetime.now().weekday()
    if wd >= 5:
        try:
            wr = subprocess.run(["python3", "/home/j/.openclaw/workspace/tools/weekend-clear.py", "--plan"],
                                capture_output=True, text=True, timeout=30)
            wtxt = (wr.stdout or "").strip()
            if wtxt:
                tag = "（周日 23:00 截止）" if wd == 6 else ""
                viol = "⚠ 未清空，今晚必须收口" if (wd == 6 and "必须做完 0 项" not in wtxt) else ""
                L.append("\n▍周末清账" + tag + ((" " + viol) if viol else ""))
                for ln in wtxt.splitlines():
                    L.append(" " + ln)
        except Exception:
            pass

    if slot == "morning":
        L.append("· 今日计划：%d 项（%s）" % (len(planned), "、".join("#%d" % r["no"] for r in planned[:8]) or "无排期"))
        for r in planned[:6]:
            L.append("   #%d %s 约%s分" % (r["no"], r["title"][:26], r["eta_min"] or "?"))
    else:
        L.append("· 今日计划 %d 项，已完成 %d 项 → 完成度 %d%%" % (len(planned), len(done_plan), pct(len(done_plan), len(planned))))
        if done_any:
            L.append("· 今日实际关账 %d 项：%s" % (len(done_any), "、".join("#%d" % r["no"] for r in done_any[:10])))
    if slot == "evening":
        L.append("· 在办 %d 项，明日优先：%s" % (len(op), "、".join("#%d" % r["no"] for r in op[:3]) or "无"))
    elif op:
        L.append("· 在办 %d 项（#%s）" % (len(op), "、".join(str(r["no"]) for r in op[:6])))

    # 五大管家
    L.append("\n▍五大管家")
    for aid, cn in BUTLERS:
        st = cs.get(aid, {"ok":0,"bad":0})
        tot = st["ok"]+st["bad"]
        rate = "—" if tot == 0 else "%d%%" % int(round(st["ok"]*100.0/tot))
        p, txt = self_review(aid, d)
        if not p:
            p, txt = self_review(aid, (datetime.date.today()-datetime.timedelta(days=1)).isoformat())
        rv, _ts = review_receipt(aid)
        tag = "自审" + (rv if rv else ("已交" if p else "缺"))
        mine = q("select count(*) n from tasks where agent=? and status not in ('done','cancelled','paused')", (aid,))
        L.append("· %s：cron 24h %d 成功/%d 失败（成功率 %s）｜%s｜在办 %d 项" % (cn, st["ok"], st["bad"], rate, tag, mine[0]["n"] if mine else 0))
        pl = plan_lines(txt) if txt else []
        for x in pl[:2]:
            L.append("   - 计划：%s" % x)

    # 资讯简报是否到点
    nf = os.path.join(WS, "state/tmp/news-brief.txt")
    if os.path.exists(nf):
        age_h = (time.time()-os.path.getmtime(nf))/3600.0
        if age_h > 8:
            L.append("\n⚠ 资讯简报已 %.0f 小时未更新（应 8:20/12:20/19:20 各一次）" % age_h)
    else:
        L.append("\n⚠ 资讯简报从未生成")

    # 逾期
    late = [r for r in op if r["due_plan"] and r["due_plan"][:10] < d]
    if late:
        L.append("\n⚠ 逾期未完成 %d 项：%s" % (len(late), "、".join("#%d" % r["no"] for r in late[:8])))

    if slot == "evening":
        L.append("\n明日 08:00 前我会把新计划发你；有异议直接回我。")
    elif slot == "morning":
        L.append("\n13:10 报午间进度，20:30 报完成度。")
    return "\n".join(L)

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("morning","noon","evening"):
        print("usage: daily-briefing.py morning|noon|evening [--dry]"); return 2
    slot = sys.argv[1]
    txt = build(slot)
    if "--dry" in sys.argv:
        print(txt); return 0
    out = os.path.join(WS, "state/tmp/brief-%s.txt" % slot)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(txt)
    # 2026-11-08 20:35 主公令：简报继续发在维护管家那边（不加账户覆盖，走 notify.sh 默认即可）
    r = subprocess.run(["bash", os.path.join(WS, "tools/notify.sh"), txt], capture_output=True, text=True)
    print("pushed rc=%d %s" % (r.returncode, (r.stderr or "")[:120]))
    return r.returncode

if __name__ == "__main__":
    sys.exit(main())
