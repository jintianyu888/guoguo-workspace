#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""schedule-review.py —— 每日定时任务体检（重复/冲突/红区/频率/时长/失联）
只读，不改任何任务。输出 state/work/schedule-review-YYYYMMDD.md
用法: python3 tools/schedule-review.py [--json]
"""
import sqlite3, json, re, sys, datetime, collections

DB="/home/j/.openclaw/state/openclaw.sqlite"
OUT="/home/j/.openclaw/workspace/state/work/schedule-review-%s.md"%datetime.date.today().strftime("%Y%m%d")

RED_ZONES=[("01:00","02:30","全量备份窗口"),("04:00","06:05","静默红线"),("07:45","08:15","重启窗口")]

def load():
    c=sqlite3.connect("file:"+DB+"?mode=ro",uri=True)
    rows=c.execute("select name,enabled,job_json,state_json from cron_jobs").fetchall()
    jobs=[]
    for name,en,js,sst in rows:
        try: j=json.loads(js) if js else {}
        except Exception: j={}
        sch=j.get("schedule") or {}
        pay=(j.get("payload") or {})
        argv=pay.get("argv") or []
        cmd=" ".join(str(a) for a in argv) if argv else str(pay.get("message") or "")[:200]
        kind=pay.get("kind") or "?"
        sig=(kind+"|"+cmd).strip()
        st={}
        try: st=json.loads(sst) if sst else {}
        except Exception: st={}
        jobs.append(dict(name=name,enabled=bool(en),agent=j.get("effectiveAgentId") or j.get("agentId") or "-",
                         kind=sch.get("kind"),expr=sch.get("expr"),every=sch.get("everyMs"),
                         at=sch.get("at"),cmd=cmd,sig=sig,kindPayload=kind,timeout=(j.get("payload") or {}).get("timeoutSeconds"),
                         last=st.get("lastRunAtMs"),status=st.get("lastRunStatus"),
                         dur=st.get("lastDurationMs")))
    return jobs

def minute_ok(expr):
    # 仅支持 5 段 cron 的分钟/小时粗判
    p=expr.split()
    if len(p)!=5: return set()
    mins=set(); hrs=set()
    for tok,acc in ((p[0],mins),(p[1],hrs)):
        for part in tok.split(","):
            if part=="*": acc.update(range(60) if acc is mins else range(24))
            elif part.startswith("*/"):
                step=int(part[2:]); acc.update(range(0,60 if acc is mins else 24,step))
            elif "-" in part:
                body,_,stp=part.partition("/")
                a,b=body.split("-")[:2]
                acc.update(range(int(a),int(b)+1,int(stp) if stp else 1))
            elif part.isdigit(): acc.add(int(part))
    return set("%02d:%02d"%(h,m) for h in hrs for m in mins)

def hhmm_to_min(s):
    h,m=s.split(":"); return int(h)*60+int(m)

def in_red(hhmm):
    t=hhmm_to_min(hhmm)
    for a,b,label in RED_ZONES:
        if hhmm_to_min(a)<=t<=hhmm_to_min(b): return label
    return None

def main():
    jobs=load()
    on=[j for j in jobs if j["enabled"]]
    off=[j for j in jobs if not j["enabled"]]
    findings=collections.defaultdict(list)

    # 1 重复：同命令同调度
    key=collections.defaultdict(list)
    for j in on:
        k=(j["sig"][:200], j["expr"] or j["every"] or j["at"])
        key[k].append(j["name"])
    for k,v in key.items():
        if len(v)>1: findings["重复任务(同命令同时间)"].append("、".join(v))

    # 1b agentTurn 同分钟撞车（耗 token）
    at_min=collections.defaultdict(list)
    for j in on:
        if j.get("kindPayload")=="agentTurn" and j["kind"]=="cron" and j["expr"]:
            for t in minute_ok(j["expr"]): at_min[t].append(j["name"])
    for t,names in sorted(at_min.items()):
        if len(names)>1: findings["同一分钟的管家任务(耗token)"].append("%s : %s"%(t,"、".join(names)))

    # 1c 重名任务
    nm=collections.Counter(j["name"] for j in on)
    for n,k in nm.items():
        if k>1: findings["重名任务(可能重复定义)"].append("%s ×%d"%(n,k))

    # 2 同分钟撞车
    per_min=collections.defaultdict(list)
    for j in on:
        if j["kind"]=="cron" and j["expr"]:
            for t in minute_ok(j["expr"]): per_min[t].append(j["name"])
    for t,names in sorted(per_min.items()):
        if len(names)>=4: findings["同一分钟≥4个任务"].append("%s : %d个 (%s)"%(t,len(names),"、".join(names[:5])))

    # 3 红区（只查低频任务；每分钟型必然跨红线，不列）
    def freq_of(j):
        if j["kind"]=="every" and j["every"]: return 86400/(j["every"]/1000)
        if j["expr"]:
            m=j["expr"].split()[0]
            if m.startswith("*/"): return 60*24/int(m[2:])
            if m=="*": return 1440
        return 1
    for j in on:
        if j["kind"]=="cron" and j["expr"] and freq_of(j)<=12:
            hit=set(filter(None,(in_red(t) for t in minute_ok(j["expr"]))))
            if hit: findings["落在红线窗口"].append("%s → %s"%(j["name"],"/".join(hit)))

    # 3b 高峰时段跑了管家任务（应只跑脚本）
    for j in on:
        if j.get("kindPayload")!="agentTurn" or j["kind"]!="cron" or not j["expr"]: continue
        p=j["expr"].split()
        if len(p)<5: continue
        mi,hh,dom,mon,dow=p
        if dow in ("0","6"): continue
        if not (mi.isdigit() and hh.isdigit()): continue
        t=int(hh)*60+int(mi)
        if 540<=t<720 or 840<=t<1080:
            findings["高峰时段跑管家任务(该挪到半价窗)"].append("%02d:%02d %s"%(t//60,t%60,j["name"]))

    # 4 高频
    for j in on:
        freq=None
        if j["kind"]=="every" and j["every"]: freq=j["every"]/60000
        elif j["expr"]:
            m=j["expr"].split()[0]
            if m.startswith("*/"): freq=int(m[2:])
            elif m=="*": freq=1
        if freq and freq<=10: findings["高频(≤10分钟)"].append("%s 每%s分钟"%(j["name"],freq))

    # 5 长任务无超时 / 超时过短
    for j in on:
        if j["dur"] and j["dur"]>300000:
            to=(j["timeout"] or 900)*1000
            if j["dur"]>to*0.8: findings["时长逼近超时"].append("%s 上次%s分钟/上限%s秒"%(j["name"],round(j["dur"]/60000,1),to//1000))

    # 6 失败/失联
    for j in on:
        if j["status"] in ("error","failed"): findings["最近一次失败"].append(j["name"])
        if not j["last"]: findings["从未运行"].append(j["name"])

    # 7 停用但仍在（清废候选）
    find_off=[j["name"] for j in off]
    if len(find_off)>40: findings["停用任务积压"].append("%d 个停用任务未清理"%len(find_off))

    if len(jobs)>100: findings["总任务数超上限(≤100)"].append("当前 %d 个，必须淘汰 %d 个"%(len(jobs),len(jobs)-100))
    lines=["# 定时任务体检 %s"%datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
           "","启用 %d / 停用 %d / 合计 %d"%(len(on),len(off),len(jobs)),""]
    order=["总任务数超上限(≤100)","高峰时段跑管家任务(该挪到半价窗)","重名任务(可能重复定义)","重复任务(同命令同时间)","同一分钟的管家任务(耗token)","同一分钟≥4个任务","落在红线窗口","高频(≤10分钟)","时长逼近超时","最近一次失败","从未运行","停用任务积压"]
    total=0
    for k in order:
        v=findings.get(k) or []
        if not v: continue
        total+=len(v)
        lines.append("## %s（%d）"%(k,len(v)))
        for x in v[:12]: lines.append("- "+x)
        if len(v)>12: lines.append("- …还有 %d 条"%(len(v)-12))
        lines.append("")
    if total==0: lines.append("未发现问题。")
    open(OUT,"w",encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines))
    print("\n报告: "+OUT)

if __name__=="__main__":
    main()
