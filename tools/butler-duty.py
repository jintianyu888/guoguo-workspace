#!/usr/bin/env python3
"""butler-duty.py v1.0 — 五大管家职责产出巡检（零 token）
用法: butler-duty.py [--date YYYY-MM-DD] [--json]
判定: 产物存在且 ≥min_bytes 且 mtime 是当日 => OK；缺 => 空转；连续3天缺 => 建议停用
"""
import json,os,sys,datetime,glob,re
W="/home/j/.openclaw/workspace"
WS={"main":W,"maint":"/home/j/openclaw-workspaces/maint","backup":"/home/j/.openclaw/workspace-backup",
    "model":"/home/j/.openclaw/workspace-model","work":"/home/j/openclaw-workspaces/work",
    "hermess":"/home/j/openclaw-workspaces/sheet-music"}
C=json.load(open(f"{W}/state/butler/contracts.json"))
day=sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else datetime.date.today().isoformat()
rows=[]
for b,spec in C["butlers"].items():
    for d in spec["duties"]:
        pat=d["artifact"].replace("<date>",day)
        paths=[]
        for root in (WS.get(b,W),W):
            p=os.path.join(root,pat)
            if p not in paths: paths.append(p)
        hit=None
        for p in paths:
            if os.path.exists(p):
                hit=p; break
        if hit:
            sz=os.path.getsize(hit)
            mt=datetime.date.fromtimestamp(os.path.getmtime(hit)).isoformat()
            if sz>=d["min_bytes"] and mt==day:
                st="✅"
                if d["id"]=="selfcheck":
                    try: _t=open(hit,errors="replace").read()
                    except Exception: _t=""
                    if not any(k in _t for k in ("## 结论","【结论","## 自审结论")):
                        st="⚠空壳"
            elif sz<d["min_bytes"]: st=f"⚠薄({sz}B)"
            else: st=f"⚠旧({mt})"
            detail=f"{sz}B {mt}"
        else:
            st="❌缺"; detail="无产物"
        rows.append((b,d["id"],d["when"],st,detail,d["must"]))
def _due(when):
    m=re.search(r'(\d{1,2}):(\d{2})', when or '')
    return int(m.group(1))*60+int(m.group(2)) if m else None
_now=datetime.datetime.now()
if day==_now.date().isoformat():
    _cur=_now.hour*60+_now.minute
    _r2=[]
    for r in rows:
        d=_due(r[2])
        if r[3]!='✅' and d is not None and d>_cur:
            r=(r[0],r[1],r[2],'⏳未到点',r[4],r[5])
        _r2.append(r)
    rows=_r2
bad=[r for r in rows if r[3] not in ("✅","⏳未到点")]
print(f"管家职责巡检 {day} | 契约 {len(rows)} 项 | 达标 {len(rows)-len(bad)} | 不达标 {len(bad)}")
for r in rows:
    print(f"  {r[3]:8s} {r[0]:8s} {r[1]:10s} {r[2]:10s} {r[4]}")
if bad:
    print("\n▍不达标项（空转风险）")
    for r in bad[:12]:
        print(f"  {r[0]}·{r[1]}：{r[3]} — 要求 {r[5]}")
if "--json" in sys.argv:
    json.dump([{"butler":r[0],"duty":r[1],"state":r[3],"detail":r[4]} for r in rows],
              open(f"{W}/state/butler/duty-{day}.json","w"),ensure_ascii=False,indent=1)
sys.exit(0 if not bad else 1)
