#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""day-sheet.py —— 今日计划表（谁 几点 干啥）
用法: python3 tools/day-sheet.py [YYYY-MM-DD]
输出: state/plan/sheet-YYYYMMDD.md
"""
import json, sqlite3, datetime, sys, os
WS="/home/j/.openclaw/workspace"; DB="/home/j/.openclaw/state/openclaw.sqlite"
PD=WS+"/state/plan"
AGENT_CN={"main":"果果","print":"格格","maint":"维护管家","backup":"备份管家","model":"模型管家","work":"干活管家","security":"安全","-":"系统脚本","":'系统脚本'}

def dom_ok(dom,d):
    if dom=="*": return True
    if dom.startswith("*/"): return d%int(dom[2:])==0
    for p in dom.split(","):
        if "-" in p:
            a,b=p.split("-")[:2]
            if int(a)<=d<=int(b): return True
        elif p.isdigit() and int(p)==d: return True
    return False

def dow_ok(dow,wd):
    if dow=="*": return True
    cm={0:1,1:2,2:3,3:4,4:5,5:6,6:0}[wd]
    for p in dow.split(","):
        if p=="7" and cm==0: return True
        if p.isdigit() and int(p)<7 and int(p)==cm: return True
        if "-" in p:
            a,b=p.split("-")[:2]
            if int(a)<=cm<=int(b): return True
    return False

def today_jobs(day):
    c=sqlite3.connect("file:"+DB+"?mode=ro",uri=True)
    out=[]
    for (jid,name,en,js) in c.execute("select job_id,name,enabled,job_json from cron_jobs where enabled=1"):
        j=json.loads(js or "{}"); sch=j.get("schedule") or {}; pay=j.get("payload") or {}
        if sch.get("kind")!="cron" or not sch.get("expr"): continue
        p=sch["expr"].split()
        if len(p)<5: continue
        mi,hh,dom,mon,dow=p
        if not dom_ok(dom,day.day) or not dow_ok(dow,day.weekday()): continue
        agent=j.get("agentId") or j.get("effectiveAgentId") or "-"
        kind=pay.get("kind") or "?"
        freq=None
        if mi.startswith("*/"): freq=int(mi[2:])
        elif mi=="*": freq=1
        times=[]
        if freq is not None:
            hhs=[int(hh)] if hh.isdigit() else list(range(24))
            for h in hhs:
                for m in range(0,60,freq): times.append("%02d:%02d"%(h,m))
        else:
            hhs=[int(hh)] if hh.isdigit() else ([int(x) for x in hh.split(",")] if hh.replace(",","").isdigit() else [])
            mm=[int(x) for x in mi.split(",")] if mi.replace(",","").isdigit() else [0]
            for h in hhs:
                for m in mm: times.append("%02d:%02d"%(h,m))
        for t in times:
            out.append((t,name,agent,freq,kind))
    return sorted(out)

def main_items(n=5):
    try:
        items=[i for i in json.load(open(WS+"/state/tasks/tasks.json",encoding="utf-8"))["items"]
               if (i.get("status") or "").lower() not in ("done","closed","cancelled")
               and "待拍板" not in (i.get("title") or "")]
    except Exception: return []
    import datetime as _dt
    today=_dt.date.today().isoformat()
    def key(i):
        d=str(i.get('due_plan') or '')
        if not d: return (2,'9999')
        return (0 if d[:10] < today else (1 if d[:10]==today else 2), d)
    items.sort(key=key)
    return items[:n]

def overdue_items():
    try:
        items=[i for i in json.load(open(WS+'/state/tasks/tasks.json',encoding='utf-8'))['items']
               if (i.get('status') or '').lower() not in ('done','closed','cancelled')]
    except Exception: return []
    import datetime as _dt
    today=_dt.date.today().isoformat()
    return [i for i in items if str(i.get('due_plan') or '')[:10] < today]

def main():
    day=datetime.date.today()
    if len(sys.argv)>1 and sys.argv[1][:4].isdigit():
        day=datetime.datetime.strptime(sys.argv[1],"%Y-%m-%d").date()
    os.makedirs(PD,exist_ok=True)
    rows=today_jobs(day)
    # 高频任务折叠
    freq=[(n,a,g) for (t,n,a,g,k) in rows if g]
    once=[(t,n,a,k) for (t,n,a,g,k) in rows if not g]
    human=[(t,n,a) for (t,n,a,k) in once if k!="command" or a not in ("-","")]
    auto=[(t,n) for (t,n,a,k) in once if (k=="command" and a in ("-",""))]
    human=[x for x in human if x[2] not in ("-","")]
    lines=["# 今日安排 %s（周%s）"%(day.strftime("%Y-%m-%d"),"一二三四五六日"[day.weekday()]),""]
    lines.append("## 一、管家出场（需要人盯的）")
    seen=set(); cnt=0
    for t,n,a in sorted(human):
        k=(t,n)
        if k in seen: continue
        seen.add(k); cnt+=1
        lines.append("- %s %s · %s"%(t, AGENT_CN.get(a,a), n))
    if cnt==0: lines.append("- 今天没有管家级任务")
    lines.append("")
    lines.append("## 二、系统自动跑（出问题我才管）")
    lines.append("- 共 %d 项：%s"%(len(set(n for _,n in auto)), "、".join(sorted(set(n for _,n in auto))[:14]) + ("…" if len(set(n for _,n in auto))>14 else "")))
    od=overdue_items()
    if od:
        lines.append("## 一·五、逾期未完成（%d 项，先补再开新）"%len(od))
        for it in od[:8]:
            lines.append("- #%s %s · 原计划 %s"%(it.get("no","?"),(it.get("title") or "")[:50],str(it.get("due_plan") or "")[5:16]))
        lines.append("")
    lines.append("")
    if freq:
        agg={}
        for n,a,g in freq:
            agg.setdefault(g,{}).setdefault(a,set()).add(n)
        lines.append("## 二、高频巡检（合并列出，不必逐条盯）")
        for g in sorted(agg):
            for a,names in agg[g].items():
                lines.append("- 每 %d 分钟 · %s：%s"%(g, AGENT_CN.get(a,a), "、".join(sorted(names))))
        lines.append("")
    items=main_items()
    slots=["09:30","10:30","11:30","14:30","15:30","16:30"]
    lines.append("## 三、我的主攻（这几件必须今天出结果）")
    if not items: lines.append("- 今日无主攻项")
    for i,it in enumerate(items):
        dp=str(it.get("due_plan") or ""); eta=it.get("eta_min") or 0
        extra=(" · 计划 "+dp[5:16]+" · 约"+str(eta)+"分") if dp else " · 未排期"
        lines.append("- %s #%s %s%s"%(slots[i] if i<len(slots) else "机动", it.get("no","?"), (it.get("title") or "")[:60], extra))
    lines.append("")
    lines.append("## 四、达标口径")
    lines.append("- 主攻项逐条报结果；没做完的写明卡在哪、明天接不接")
    out=PD+"/sheet-%s.md"%day.strftime("%Y%m%d")
    open(out,"w",encoding="utf-8").write("\n".join(lines)+"\n")
    print("\n".join(lines)); print("\n文件: "+out)

if __name__=="__main__": main()
