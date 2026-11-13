#!/usr/bin/env python3
import json,subprocess,os,time,datetime
OC=os.path.expanduser("~/.npm-global/bin/openclaw")
ids={"ed4c9481-a255-495d-b856-77620658bd5e":"告警双审","7343f9f0-c9e9-496b-9b6d-743bbadc153a":"果果助手双审",
 "564aeb60-60c4-4e9f-92cb-654c4f579d4a":"周计划","2fd10b3c-1882-4789-8ec1-3f1f7d41bba4":"记忆体检",
 "330261ca-5dcf-42fc-b2a1-c625a5cf4f69":"包升级巡检","6ec8ec62-442a-4372-a146-05300d0da962":"恢复文档审查",
 "935c9c9e-a99c-480c-bb4f-e53b0389c7df":"月结","aeeb49c3-471b-4474-b2e1-dd2883fc7394":"年结"}
cut=int(datetime.datetime(2026,11,13,13,29).timestamp()*1000)
for jid,nm in ids.items():
    try:
        out=subprocess.run([OC,"cron","runs",jid,"--limit","6","--json"],capture_output=True,text=True,timeout=60).stdout
        e=json.loads(out).get("entries",[])
    except Exception as ex:
        print(nm,"ERR",ex); continue
    new=[x for x in e if x.get("ts",0)>=cut]
    if not new: print(f"{nm}: 今日无新运行记录"); continue
    for x in sorted(new,key=lambda y:y["ts"])[-3:]:
        t=datetime.datetime.fromtimestamp(x["ts"]/1000).strftime("%H:%M")
        print(f"{nm} {t} {x.get('action')} {x.get('status')} {x.get('completionStatus') or ''} {(x.get('summary') or '')[:40]}")
