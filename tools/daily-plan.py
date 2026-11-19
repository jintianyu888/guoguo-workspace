#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""daily-plan.py —— 明日计划预排 + 今日计划对账
用法:
  python3 tools/daily-plan.py            # 生成明日计划 state/plan/plan-YYYYMMDD.md
  python3 tools/daily-plan.py --score    # 对账今日计划，写 state/plan/score-YYYYMMDD.md
  python3 tools/daily-plan.py --week     # 周计划概览
原则:
  - 计划只排"塞得下"的量：重活上限 MAX_HEAVY=5 项，其余进候补
  - 每项都带验收方式，done 判定靠证据不靠嘴
  - 未完成项自动结转，连续 3 天结转 -> 标 STALE 并建议拆分或砍掉
"""
import json, sqlite3, datetime, os, sys, collections

WS = "/home/j/.openclaw/workspace"
TASKS = WS + "/state/tasks/tasks.json"
CRONDB = "/home/j/.openclaw/state/openclaw.sqlite"
LEDGER = WS + "/state/ledger/ledger.db"
PLANDIR = WS + "/state/plan"
CAPFILE = PLANDIR + "/capacity.json"
def cap():
    try:
        return max(2, min(6, int(json.load(open(CAPFILE))["max_heavy"])))
    except Exception:
        return 5
MAX_HEAVY = 5
RED = [("01:00","02:30","备份"),("04:00","06:05","静默"),("07:45","08:15","重启窗")]
PEAK = [("09:00","12:00"),("14:00","18:00")]

def ensure():
    os.makedirs(PLANDIR, exist_ok=True)

def load_tasks():
    try:
        d = json.load(open(TASKS, encoding="utf-8"))
    except Exception:
        return []
    out = []
    for it in d.get("items", []):
        st = (it.get("status") or "").lower()
        if st in ("done","closed","cancelled","cancel"): continue
        out.append(it)
    return out

def load_cron(day):
    """返回当天会触发的任务 [(hhmm,name,kind,freq)]"""
    rows=[]
    try:
        c=sqlite3.connect("file:"+CRONDB+"?mode=ro", uri=True)
        for (name, en, js) in c.execute("select name,enabled,job_json from cron_jobs where enabled=1"):
            j=json.loads(js or "{}"); sch=j.get("schedule") or {}
            pay=j.get("payload") or {}
            kind=pay.get("kind") or "?"
            if sch.get("kind")=="cron" and sch.get("expr"):
                p=sch["expr"].split()
                if len(p)<5: continue
                mi,hh=p[0],p[1]; dom=p[2]; mon=p[3]; dow=p[4]
                # 判断当天是否可能触发（粗判）
                wd=day.weekday()  # 0=Mon
                cronmap={0:1,1:2,2:3,3:4,4:5,5:6,6:0}
                if dow!="*":
                    allowed=set()
                    for part in dow.split(","):
                        if part.isdigit(): allowed.add(int(part)%7)
                        elif "-" in part:
                            a,b=part.split("-")[:2]; allowed.update(range(int(a),int(b)+1))
                        elif part=="7": allowed.add(0)
                    if cronmap[wd] not in allowed: continue
                def dom_ok(d):
                    if dom=="*": return True
                    if dom.startswith("*/"): return d % int(dom[2:])==0
                    for part in dom.split(","):
                        if "-" in part:
                            a,b=part.split("-")[:2]
                            if int(a)<=d<=int(b): return True
                        elif part.isdigit() and int(part)==d: return True
                    return False
                if not dom_ok(day.day): continue
                freq = "*" in mi and "*/" not in mi
                hhs = list(range(24)) if hh=="*" else ([int(hh)] if hh.isdigit() else None)
                if hhs is None:
                    if hh.startswith("*/"):
                        stp=int(hh[2:]); hhs=list(range(0,24,stp))
                    else: hhs=[]
                if freq: rows.append(("全天",name,kind,"高频")); continue
                for h in hhs:
                    mm = 0 if mi=="0" else None
                    if mi.isdigit(): rows.append(("%02d:%02d"%(h,int(mi)),name,kind,""))
                    elif mi.startswith("*/"): rows.append(("%02d:*"%h,name,kind,"高频%s"%mi))
    except Exception as e:
        rows.append(("00:00","[cron读取失败:%s]"%e,"?",""))
    return rows

def in_red(t):
    try:
        h,m=t.replace("*","0").split(":"); x=int(h)*60+int(m)
    except Exception: return None
    for a,b,l in RED:
        ah,am=a.split(":"); bh,bm=b.split(":")
        if int(ah)*60+int(am) <= x <= int(bh)*60+int(bm): return l
    return None

def plan_for(day):
    ensure()
    tasks = load_tasks()
    # 优先级：有 notes 里带 P0/P1 的、更新时间早的（欠账久的先做）
    def prio(it):
        n = (it.get("notes") or "")
        p = 0
        if "P0" in n: p -= 30
        if "P1" in n: p -= 20
        if it.get("prio") in (1,"1","high","P1"): p -= 20
        if it.get("prio") in (0,"0","P0","high"): p -= 30
        return p
    tasks.sort(key=prio)
    blocked = [t for t in tasks if "待拍板" in (t.get("title") or "") or "待决策" in (t.get("title") or "")]
    free = [t for t in tasks if t not in blocked]
    MAX_HEAVY = cap()
    heavy = free[:MAX_HEAVY]
    backlog = free[MAX_HEAVY:]

    cron = load_cron(day)
    fixed_major = [r for r in cron if r[2] in ("agentTurn","heartbeat") or "备份" in r[1]]
    conflicts = [(t,n) for (t,n,k,f) in cron if in_red(t or "") and f not in ("高频",)]

    wd = "一二三四五六日"[day.weekday()]
    lines = ["# 明日计划 %s（周%s）"%(day.strftime("%Y-%m-%d"), wd), ""]
    lines.append("## 一、固定任务（已排好，不占人力）")
    seen=set()
    for t,n,k,f in sorted(fixed_major):
        key=(n,)
        if key in seen: continue
        seen.add(key)
        lines.append("- %s %s%s"%(t, n, "（%s）"%f if f else ""))
    if not fixed_major: lines.append("- 无")
    lines.append("")
    if blocked:
        lines.append("## 零、等你一句话（%d 项，不占用我的工时，你点头就能推）"%len(blocked))
        for t in blocked[:6]:
            lines.append("- #%s %s"%(t.get("no","?"), (t.get("title") or "").replace("【待拍板】","")[:56]))
        if len(blocked)>6: lines.append("- …还有 %d 项"%(len(blocked)-6))
        lines.append("")
    lines.append("## 二、今日主攻（上限 %d 项，做完才算达标）"%MAX_HEAVY)
    if not heavy: lines.append("- 待办清空，无主攻项")
    for i,it in enumerate(heavy,1):
        v = it.get("verify") or it.get("verify_cmd") or "人工确认"
        lines.append("%d. [ ] #%s %s ｜验收：%s"%(i, it.get("no","?"), (it.get("title") or "")[:60], v))
    lines.append("")
    if backlog:
        lines.append("## 三、候补（今天不排，别硬塞）%d 项"%len(backlog))
        for it in backlog[:8]:
            lines.append("- #%s %s"%(it.get("no","?"), (it.get("title") or "")[:50]))
        if len(backlog)>8: lines.append("- …还有 %d 项"%(len(backlog)-8))
        lines.append("")
    if conflicts:
        lines.append("## 四、时间冲突（需处理）")
        for t,n in conflicts[:10]:
            lines.append("- %s %s 落在「%s」窗口"%(t,n,in_red(t)))
        lines.append("")
    lines.append("## 五、达标口径")
    lines.append("- 主攻项 5 项全绿 = 100%%；4 项 80%%；≤3 项视为计划超载，次日必须减量")
    lines.append("- 结转项连续 3 天未动 → 标 STALE，拆小或砍掉")
    out = PLANDIR + "/plan-%s.md"%day.strftime("%Y%m%d")
    open(out,"w",encoding="utf-8").write("\n".join(lines)+"\n")
    return out, "\n".join(lines)

def score(today):
    """对账：昨日计划 vs 实际（看 tasks.json 状态与 cron 失败）"""
    y = today - datetime.timedelta(days=1)
    pfile = PLANDIR + "/plan-%s.md"%y.strftime("%Y%m%d")
    lines = ["# 计划对账 %s（评估 %s 的计划）"%(today.strftime("%Y-%m-%d"), y.strftime("%Y-%m-%d")), ""]
    if not os.path.exists(pfile):
        lines.append("昨日没有生成计划，无法对账。")
    else:
        txt = open(pfile,encoding="utf-8").read()
        planned = [l for l in txt.splitlines() if l.startswith(("1. [ ]","2. [ ]","3. [ ]","4. [ ]","5. [ ]"))]
        tasks = {t.get("no"):t for t in load_tasks()}
        done = 0
        for l in planned:
            no = l.split("#")[1].split()[0] if "#" in l else "?"
            t = tasks.get(no) or tasks.get(int(no) if no.isdigit() else -1)
            st = (t or {}).get("status","?")
            ok = st in ("done","closed")
            done += 1 if ok else 0
            lines.append("- %s #%s %s"%(("[x]" if ok else "[ ]"), no, st))
        rate = round(100*done/max(len(planned),1))
        lines.append("")
        lines.append("完成率：%d%%（%d/%d）"%(rate, done, len(planned)))
        old = cap()
        if rate < 60:
            new = max(2, old-1); lines.append("结论：计划超载，主攻上限 %d → %d 项"%(old,new))
        elif rate >= 90:
            new = min(6, old+1); lines.append("结论：完成率 %d%%，主攻上限 %d → %d 项"%(rate,old,new))
        else:
            new = old; lines.append("结论：完成率 %d%%，上限保持 %d 项"%(rate,old))
        json.dump({"max_heavy": new, "updated": today.isoformat(), "last_rate": rate},
                  open(CAPFILE,"w"), ensure_ascii=False)
    lines.append("")
    lines.append("## 昨日失败任务")
    try:
        c=sqlite3.connect("file:"+CRONDB+"?mode=ro", uri=True)
        for (name,) in c.execute("select name from cron_jobs where enabled=1 and state_json like '%\"lastRunStatus\":\"error\"%'"):
            lines.append("- "+name)
    except Exception: pass
    out = PLANDIR + "/score-%s.md"%today.strftime("%Y%m%d")
    os.makedirs(PLANDIR, exist_ok=True)
    open(out,"w",encoding="utf-8").write("\n".join(lines)+"\n")
    return out, "\n".join(lines)

def main():
    today = datetime.date.today()
    if "--score" in sys.argv:
        out, txt = score(today)
    elif "--week" in sys.argv:
        ensure()
        lines=["# 周计划 %s"%today.strftime("%Y-%m-%d"),""]
        for i in range(7):
            d=today+datetime.timedelta(days=i)
            cron=[r for r in load_cron(d) if r[2] in ("agentTurn","heartbeat")]
            red=[r[0] for r in load_cron(d) if in_red(r[0] or "") and r[3]!="高频" and r[2]!="command"]
            lines.append("- %s 周%s：管家任务 %d 个%s"%(d.strftime("%m-%d"),"一二三四五六日"[d.weekday()],len(set(n for _,n,_,_ in cron)),"，红线冲突 "+str(len(red)) if red else ""))
        lines.append("")
        lines.append("待办总量：%d 项；按每日 5 项上限需 %d 天"%(len(load_tasks()), -(-len(load_tasks())//MAX_HEAVY)))
        out=PLANDIR+"/week-%s.md"%today.strftime("%Y%m%d")
        open(out,"w",encoding="utf-8").write("\n".join(lines)+"\n")
        txt="\n".join(lines)
    else:
        out, txt = plan_for(today + datetime.timedelta(days=1))
    print(txt)
    print("\n文件: "+out)

if __name__ == "__main__":
    main()
