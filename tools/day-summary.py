#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""day-summary.py —— 今日总结（计划 vs 实际）
用法: python3 tools/day-summary.py [YYYY-MM-DD]
输出: state/plan/summary-YYYYMMDD.md
"""
import json, sqlite3, datetime, sys, os
WS="/home/j/.openclaw/workspace"; DB="/home/j/.openclaw/state/openclaw.sqlite"
PD=WS+"/state/plan"
AGENT_CN={"main":"果果","print":"格格","maint":"维护管家","backup":"备份管家","model":"模型管家","work":"干活管家","-":"系统脚本"}

def main():
    day=datetime.date.today()
    if len(sys.argv)>1 and sys.argv[1][:4].isdigit():
        day=datetime.datetime.strptime(sys.argv[1],"%Y-%m-%d").date()
    start=int(datetime.datetime.combine(day,datetime.time(0,0)).timestamp()*1000)
    end=start+86400000
    c=sqlite3.connect("file:"+DB+"?mode=ro",uri=True)
    jobs={r[0]:(r[1],r[2]) for r in c.execute("select job_id,name,job_json from cron_jobs")}
    ok=[];bad=[]
    for jid,st,err in c.execute("select job_id,status,error_text from cron_run_receipts where started_at_ms>=? and started_at_ms<?",(start,end)):
        nm=jobs.get(jid,("?"+str(jid)[:8],))[0]
        if st=="ok": ok.append(nm)
        else: bad.append((nm,(err or st or "")[:60]))
    lines=["# 今日总结 %s（周%s）"%(day.strftime("%Y-%m-%d"),"一二三四五六日"[day.weekday()]),""]
    lines.append("## 一、跑完的（%d 次）"%len(ok))
    uniq=sorted(set(ok))
    lines.append("、".join(uniq[:40]) if uniq else "无")
    lines.append("")
    lines.append("## 二、失败的（%d 次）"%len(bad))
    if not bad: lines.append("无失败")
    seen=set()
    for nm,err in bad:
        if nm in seen: continue
        seen.add(nm); lines.append("- %s ｜%s"%(nm,err))
    lines.append("")
    # 主攻项
    try:
        items=json.load(open(WS+"/state/tasks/tasks.json",encoding="utf-8"))["items"]
        focus=[i for i in items if (i.get("updated") or "").startswith(day.isoformat())]
        lines.append("## 三、今天动过的事（%d 条）"%len(focus))
        for i in focus[:12]:
            lines.append("- [%s] #%s %s"%(i.get("status"), i.get("no"), (i.get("title") or "")[:56]))
        if not focus: lines.append("- 台账今天没有任何状态更新 —— 属于空转，需要追责")
    except Exception as e:
        lines.append("- 台账读取失败: %s"%e)
    lines.append("")
    # 逾期项 + 原因（主公 2026-11-07 令：逾期必须写原因）
    try:
        tdb=sqlite3.connect("file:"+WS+"/state/tasks/tasks.db?mode=ro",uri=True)
        rows=tdb.execute("select no,title,due_plan,slip_reason,status from tasks where status not in ('done','cancelled') and due_plan is not null and substr(due_plan,1,10) <= ? order by due_plan",(day.isoformat(),)).fetchall()
        od=[r for r in rows if r[2][:10] < day.isoformat()]
        done_today=tdb.execute("select count(*) from tasks where status='done' and substr(updated,1,10)=?",(day.isoformat(),)).fetchone()[0]
        lines.append("## 三·五、今日完成 %d 项 / 逾期 %d 项"%(done_today,len(od)))
        for no,title,dp,reason,st in od:
            lines.append("- #%s %s（原计划 %s）→ %s"%(no,(title or "")[:46],dp[5:16],("原因: "+reason) if reason else "**缺原因，今晚必须补**"))
        if not od: lines.append("- 无逾期")
        lines.append("")
    except Exception as e:
        lines.append("- 逾期统计失败: %s"%e)
    lines.append("## 四、结论")
    lines.append("- 定时任务成功率 %d%%（%d 成功 / %d 失败）"%(round(100*len(ok)/max(len(ok)+len(bad),1)), len(ok), len(bad)))
    # 计划分（2026-11-07 主公令：提前加分、逾期扣分）
    try:
        import subprocess
        _sc=subprocess.run(["python3",WS+"/tools/plan-score.py"],capture_output=True,text=True,timeout=120).stdout.strip()
        if _sc: lines.append(""); lines.append(_sc)
    except Exception as e:
        lines.append("- 计划分计算失败: %s"%e)
    out=PD+"/summary-%s.md"%day.strftime("%Y%m%d")
    os.makedirs(PD,exist_ok=True)
    open(out,"w",encoding="utf-8").write("\n".join(lines)+"\n")
    print("\n".join(lines)); print("\n文件: "+out)

if __name__=="__main__": main()
