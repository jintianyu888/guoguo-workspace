#!/usr/bin/env python3
"""peer-verdict.py v1.0 — 汇总五家互审结论（零 token）
读各家 peer-audit 落盘文件里的「审定：X 合格|不合格」行，输出台账。"""
import os,re,glob,json,datetime
W="/home/j/.openclaw/workspace"; D=datetime.date.today().isoformat()
SRC={
 "maint":  W+"/state/maint/peer-audit.md",
 "backup": "/home/j/.openclaw/workspace-backup/state/reports/peer-audit.md",
 "model":  "/home/j/.openclaw/workspace-model/state/reports/peer-audit.md",
 "work":   "/home/j/openclaw-workspaces/work/state/reports/peer-audit.md",
 "hermess":"/home/j/openclaw-workspaces/sheet-music/state/reports/peer-audit.md",
}
PAIR={"maint":"备份","backup":"维护","model":"干活","work":"模型","hermess":"果果"}
rows=[];bad=0
for k,p in SRC.items():
    if not os.path.exists(p):
        rows.append((k,PAIR[k],"❌未提交","无文件")); bad+=1; continue
    txt=open(p,errors="ignore").read()
    age=datetime.date.fromtimestamp(os.path.getmtime(p)).isoformat()
    m=re.findall(r"审定[:：]\s*\S*?\s*(合格|不合格)",txt)
    verdict=m[-1] if m else "⚠无结论"
    ev=""
    em=re.search(r"依据[:：](.{0,40})",txt) or re.search(r"问题[:：](.{0,40})",txt)
    if em: ev=em.group(1).replace("\n"," ").strip()
    if verdict!="合格": bad+=1
    rows.append((k,PAIR[k],verdict,("旧:"+age if age!=D else ev[:36])))
print(f"互审结论 {D}｜合格 {len(rows)-bad}/{len(rows)}")
for k,peer,v,ev in rows:
    print(f"  {k:8s} → {peer:4s} {v:6s} {ev}")
out={"date":D,"rows":[{"auditor":r[0],"peer":r[1],"verdict":r[2],"note":r[3]} for r in rows],"fail":bad}
json.dump(out,open(W+"/state/butler/verdict-"+D+".json","w"),ensure_ascii=False,indent=1)
raise SystemExit(0 if bad==0 else 1)
