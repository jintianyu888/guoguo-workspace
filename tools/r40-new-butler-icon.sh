#!/bin/bash
# r40-new-butler-icon.sh —— R40 检查：每个飞书管家在 registry 里都有头像记录，且图存在
cd /home/j/.openclaw/workspace || exit 2
python3 - <<"PY"
import json,os,sys
W="/home/j/.openclaw/workspace"
cfg=json.load(open("/home/j/.openclaw/openclaw.json"))
acc=cfg["channels"]["feishu"]["accounts"]
reg=json.load(open(W+"/state/icons/registry.json")) if os.path.exists(W+"/state/icons/registry.json") else {}
missing=[]; gone=[]
for k,v in acc.items():
    app=v.get("appId")
    if app not in reg: missing.append(k+":"+str(app)); continue
    p=reg[app].get("png","")
    if not p or not os.path.exists(p): gone.append(k)
if missing or gone:
    print("RED 缺头像记录:",len(missing),"→",missing[:6],"| 图文件缺失:",gone[:6])
    sys.exit(1)
print("GREEN R40",len(acc),"个管家均有头像记录与本地图")
PY
