#!/usr/bin/env python3
"""群晖分类仓库占用报表（只读）。用法: python3 nas-repo-report.py"""
import json, os, subprocess
NAS="nas"
STATE=os.path.expanduser("~/.openclaw/workspace/state/nas-repo-state.json")
LABEL={"main":"🎙️麦克","mom-health":"🩺妈妈健康","tax":"🧾税务","fitness":"🏃运动","wealth":"💰理财",
 "piano-app":"🎹钢琴APP","health-wang":"🩺王爸爸","health-jin":"🩺靳爸爸","health-wife":"🩺媳妇",
 "health-self":"🩺本人","calendar":"📅日程","doll-brand":"🧸玩偶品牌","piano-room":"🎹琴房","cooking":"🍳做饭",
 "sheet-music":"🎼乐谱","print":"🖨️打印","class-schedule":"🗓️排课","script-mystery":"🎭剧本杀",
 "health-doudou":"🩺豆豆健康","schedule-doudou":"📅豆豆日程","doudou-apply":"🎓豆豆申请"}
try:
    r=subprocess.run(["ssh","-o","BatchMode=yes","-o","ConnectTimeout=10",NAS,
                      "du -sk ~/archive/jinyu/migrated-20261102/openclaw-repos/* 2>/dev/null"],capture_output=True,text=True,timeout=120)
    rows=[]
    for line in (r.stdout or "").splitlines():
        pr=line.split("\t")
        if len(pr)==2: rows.append((os.path.basename(pr[1].strip()), int(pr[0])/1024))
    if not rows:
        print("群晖分类仓库：暂不可用"); raise SystemExit
    prev={}
    if os.path.exists(STATE):
        try: prev=json.load(open(STATE))
        except Exception: prev={}
    rows.sort(key=lambda x:-x[1])
    print("【群晖分类仓库占用】")
    for aid,mb in rows:
        old=prev.get(aid)
        d = "" if old is None else (f"（{'+' if mb-old>=0 else ''}{mb-old:.1f} MB）" if abs(mb-old)>=0.1 else "（持平）")
        print(f"{LABEL.get(aid,aid)} · {mb:.1f} MB {d}")
    print(f"合计：{sum(m for _,m in rows):.0f} MB · 共 {len(rows)} 个仓库")
except Exception as e:
    print(f"群晖分类仓库：暂不可用（{type(e).__name__}）")
