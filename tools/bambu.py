#!/usr/bin/env python3
"""Bambu Lab 局域网直连（MQTT/TLS 8883）。
用法:
  python3 tools/bambu.py status
  python3 tools/bambu.py watch [秒]
  python3 tools/bambu.py save --ip X --serial Y --code Z
  python3 tools/bambu.py raw
凭据: state/secrets/bambu.json {"ip","serial","code"} 600
"""
import json, os, ssl, sys, time
from pathlib import Path
import paho.mqtt.client as mqtt

WS = Path(__file__).resolve().parent.parent
CRED = WS / "state" / "secrets" / "bambu.json"

def load_cred():
    if not CRED.exists():
        sys.exit("缺凭据: tools/bambu.py save --ip <IP> --serial <序列号> --code <访问码>")
    d = json.loads(CRED.read_text())
    for k in ("ip","serial","code"):
        if not d.get(k): sys.exit("凭据缺字段 "+k)
    return d

def cmd_save(a):
    ip=serial=code=None; it=iter(a)
    for x in it:
        if x=="--ip": ip=next(it,None)
        elif x=="--serial": serial=next(it,None)
        elif x=="--code": code=next(it,None)
    if not (ip and serial and code): sys.exit("用法: save --ip <IP> --serial <序列号> --code <访问码>")
    CRED.parent.mkdir(parents=True, exist_ok=True)
    CRED.write_text(json.dumps({"ip":ip,"serial":serial,"code":code}))
    os.chmod(CRED,0o600); print("已保存凭据 ->", CRED, "(600)")

STATE_MAP={"IDLE":"空闲","PREPARE":"准备","RUNNING":"打印中","PAUSE":"暂停","FINISH":"完成","FAILED":"失败"}

def summarize(p):
    g=p.get("print",p)
    if not isinstance(g,dict): return "无 print 数据"
    st=g.get("gcode_state","?")
    out=["状态: %s (%s)"%(STATE_MAP.get(st,st),st)]
    if g.get("mc_percent") is not None:
        out.append("进度: %s%% 剩余 %s 分钟"%(g.get("mc_percent"),g.get("mc_remaining_time")))
    if g.get("subtask_name"): out.append("任务: "+str(g.get("subtask_name")))
    temps=[]
    for k,l in (("nozzle_temper","喷嘴"),("bed_temper","热床"),("chamber_temper","腔体")):
        if g.get(k) is not None:
            tgt=g.get(k.replace("_temper","_target"))
            temps.append("%s %.0f/%s C"%(l,g.get(k),tgt if tgt is not None else "-"))
    if temps: out.append("温度: "+"  ".join(temps))
    ams=g.get("ams") if isinstance(g.get("ams"),dict) else None
    if ams:
        for unit in ams.get("ams",[]):
            for tray in unit.get("tray",[]):
                if tray.get("tray_type"):
                    out.append("AMS%s-槽%s: %s %s 余量%s%%"%(unit.get("id"),tray.get("id"),tray.get("tray_type"),tray.get("tray_color",""),tray.get("remain","?")))
    if g.get("hms"): out.append("HMS 告警: %d 条"%len(g["hms"]))
    if g.get("print_error"): out.append("错误码: %s"%g.get("print_error"))
    return "\n".join(out)

def run(seconds=None, raw=False):
    c=load_cred(); serial=c["serial"]; got={}
    def on_connect(cl,u,f,rc,props=None): cl.subscribe("device/%s/report"%serial, qos=0)
    def on_message(cl,u,msg):
        try: got.update(json.loads(msg.payload.decode("utf-8","ignore")))
        except Exception: return
    cl=mqtt.Client(client_id="guoguo-%d"%os.getpid(), protocol=mqtt.MQTTv311)
    cl.username_pw_set("bblp", c["code"])
    ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
    cl.tls_set_context(ctx); cl.on_connect=on_connect; cl.on_message=on_message
    try: cl.connect(c["ip"],8883,20)
    except Exception as e:
        sys.exit("连不上 %s:8883 -> %s\n检查: 开机 / 局域网模式 / IP"%(c["ip"],e))
    cl.loop_start(); time.sleep(1.5)
    cl.publish("device/%s/request"%serial, json.dumps({"pushing":{"sequence_id":"1","command":"pushall"}}))
    deadline=time.time()+(seconds if seconds else 15)
    while time.time()<deadline and not got: time.sleep(0.3)
    time.sleep(0.5); cl.loop_stop(); cl.disconnect()
    if not got: sys.exit("已连接但无数据: 序列号可能不对")
    print(json.dumps(got,ensure_ascii=False,indent=1) if raw else summarize(got))

if __name__=="__main__":
    a=sys.argv[1:]
    if not a: sys.exit(__doc__)
    cmd=a[0]
    if cmd=="save": cmd_save(a[1:])
    elif cmd=="status": run()
    elif cmd=="watch": run(seconds=int(a[1]) if len(a)>1 else 30)
    elif cmd=="raw": run(raw=True)
    else: sys.exit(__doc__)

