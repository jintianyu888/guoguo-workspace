#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""score.py —— 干活记分（干完记分，没干完也记分，没干完必须写原因）
用法:
  python3 tools/score.py score [YYYY-MM-DD]   # 当日结算，追加到 scores.jsonl
  python3 tools/score.py board                # 近 14 天榜单
  python3 tools/score.py reason <任务号> <原因> # 给未完成项补原因
规则:
  完成 +10 / 部分(+5，有推进但未收口) / 未完成 0 且必须写原因
  未完成且无原因 -5（无原因视同没交代）
  原因分类: 等拍板 / 技术阻塞 / 被挤占 / 时间不够 / 忘做 / 外部依赖
  STALE: 同一项连续 3 天未完成，额外 -3 并在榜上标红
"""
import json, os, sys, re, datetime, sqlite3, collections

WS="/home/j/.openclaw/workspace"; PD=WS+"/state/plan"
SCORES=PD+"/scores.jsonl"; TASKS=WS+"/state/tasks/tasks.json"
DB="/home/j/.openclaw/state/openclaw.sqlite"
GOOD=10; PART=5; NOREASON=-5; STALE_PEN=-3

def tasks():
    try: return {str(i.get("no")):i for i in json.load(open(TASKS,encoding="utf-8"))["items"]}
    except Exception: return {}

def plan_items(day):
    p=PD+"/plan-%s.md"%day.strftime("%Y%m%d")
    out=[]
    if os.path.exists(p):
        for l in open(p,encoding="utf-8"):
            m=re.search(r"#(\d+)", l)
            if m: out.append(m.group(1))
    if not out:  # 回退：用 sheet 的主攻
        p=PD+"/sheet-%s.md"%day.strftime("%Y%m%d")
        if os.path.exists(p):
            sec=open(p,encoding="utf-8").read().split("我的主攻")
            if len(sec)>1:
                for l in sec[1].splitlines():
                    m=re.search(r"#(\d+)", l)
                    if m: out.append(m.group(1))
    return out

def reasons_today():
    """从 tasks.json notes 里取 '未完成原因:' 当日标注"""
    r={}
    for no,t in tasks().items():
        n=t.get("notes") or ""
        if "未完成原因:" in n:
            r[no]=n.split("未完成原因:")[-1].strip()[:120]
    return r

def auto_reason(no,t):
    title=(t or {}).get("title") or ""
    notes=(t or {}).get("notes") or ""
    if "待拍板" in title or "待决策" in title: return "等拍板"
    if any(k in notes for k in ("超时","失败","报错","异常")): return "技术阻塞"
    if "paused"==((t or {}).get("status") or ""): return "被挤占"
    return "未动"

def score_day(day):
    T=tasks(); reasons=reasons_today()
    items=plan_items(day)
    prev=collections.Counter()
    if os.path.exists(SCORES):
        for l in open(SCORES,encoding="utf-8"):
            try: d=json.loads(l)
            except Exception: continue
            if d.get("status")!="done": prev[d.get("no")]+=1
    recs=[]; total=0
    for no in items:
        t=T.get(no,{})
        st=(t.get("status") or "").lower()
        upd=(t.get("updated") or "")[:10]
        done = st in ("done","closed") 
        part = st=="in_progress" and upd==day.isoformat()
        if done: pts,status=GOOD,"done"
        elif part: pts,status=PART,"partial"
        else:
            status="missed"
            why = reasons.get(no) or None
            pts = 0 if why else NOREASON
            if prev[no]>=2: pts+=STALE_PEN; status="missed_stale"
        why = reasons.get(no) or (None if done else auto_reason(no,t))
        recs.append({"date":day.isoformat(),"no":no,"title":(t.get("title") or "")[:60],
                     "status":status,"points":pts,"reason":why})
        total+=pts
    # 管家任务分：定时任务成功率
    start=int(datetime.datetime.combine(day,datetime.time(0,0)).timestamp()*1000)
    ok=bad=0
    try:
        c=sqlite3.connect("file:"+DB+"?mode=ro",uri=True)
        for st, in c.execute("select status from cron_run_receipts where started_at_ms>=? and started_at_ms<?",(start,start+86400000)):
            if st=="ok": ok+=1
            else: bad+=1
    except Exception: pass
    rate=round(100*ok/max(ok+bad,1))
    recs.append({"date":day.isoformat(),"no":"#cron","title":"定时任务成功率","status":"rate",
                 "points":round(rate/10),"rate":rate,"reason":"%d成功/%d失败"%(ok,bad)})
    total+=round(rate/10)
    os.makedirs(PD,exist_ok=True)
    # 同一天重复结算则先清掉当天旧记录
    keep=[]
    if os.path.exists(SCORES):
        for l in open(SCORES,encoding="utf-8"):
            try:
                if json.loads(l).get("date")!=day.isoformat(): keep.append(l)
            except Exception: pass
    with open(SCORES,"w",encoding="utf-8") as f:
        f.writelines(keep)
        for r in recs: f.write(json.dumps(r,ensure_ascii=False)+"\n")
    return recs,total

def render(recs,total,day):
    L=["# 记分 %s"%day.isoformat(),""]
    miss=0
    for r in recs:
        if r["status"]=="rate":
            L.append("- 定时任务成功率 %s%%（%s）得 %+d"%(r.get("rate","?"),r["reason"],r["points"])); continue
        tag={"done":"完成","partial":"部分","missed":"未完成","missed_stale":"未完成(连续)"}[r["status"]]
        L.append("- #%s %s ｜%s %+d ｜原因：%s"%(r["no"], r["title"][:34], tag, r["points"], r["reason"] or "未说明"))
        if r["status"].startswith("missed"): miss+=1
    L.append("")
    L.append("今日合计 %+d 分；未完成 %d 项"%(total,miss))
    if any((r["reason"] in (None,"未动")) and r["status"].startswith("missed") for r in recs):
        L.append("⚠ 有未完成项没写原因（默认按 -5 记），需要补：state/plan/scores.jsonl")
    return "\n".join(L)

def board():
    if not os.path.exists(SCORES): return "还没有记分记录"
    agg=collections.defaultdict(int); days=collections.Counter(); miss=collections.Counter()
    for l in open(SCORES,encoding="utf-8"):
        try: d=json.loads(l)
        except Exception: continue
        agg[d["date"]]+=d["points"]; days[d["date"]]+=1
        if d["status"].startswith("missed"): miss[d["date"]]+=1
    L=["# 记分榜（近 14 天）",""]
    for dt in sorted(agg)[-14:]:
        L.append("- %s 得分 %+d（未完成 %d 项）"%(dt,agg[dt],miss[dt]))
    avg=round(sum(agg.values())/max(len(agg),1),1)
    L.append("")
    L.append("日均 %+d 分"%avg)
    return "\n".join(L)

def add_reason(no,why):
    # 写入 tasks.json 的 notes（保留原 notes）
    try:
        d=json.load(open(TASKS,encoding="utf-8"))
    except Exception as e:
        return "读取失败: %s"%e
    hit=False
    for it in d["items"]:
        if str(it.get("no"))==str(no):
            n=it.get("notes") or ""
            if "未完成原因:" in n: n=n.split("未完成原因:")[0]
            it["notes"]=n.rstrip("｜ ")+"｜未完成原因:"+why
            hit=True
    if not hit: return "没找到任务 #%s"%no
    d["updated"]=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    json.dump(d,open(TASKS,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
    return "已记录 #%s 原因：%s"%(no,why)

def main():
    a=sys.argv[1:]
    day=datetime.date.today()
    if a and a[0]=="score":
        if len(a)>1 and a[1][:4].isdigit(): day=datetime.datetime.strptime(a[1],"%Y-%m-%d").date()
        recs,total=score_day(day)
        out=render(recs,total,day)
        open(PD+"/score-%s.md"%day.strftime("%Y%m%d"),"w",encoding="utf-8").write(out+"\n")
        print(out)
    elif a and a[0]=="board":
        print(board())
    elif a and a[0]=="reason" and len(a)>2:
        print(add_reason(a[1]," ".join(a[2:])))
    else:
        print(__doc__)

if __name__=="__main__": main()
