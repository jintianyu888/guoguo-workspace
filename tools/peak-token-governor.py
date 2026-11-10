#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""peak-token-governor.py —— 高峰时段自动暂停"烧 token 的任务"，半价窗恢复

规则（主公 2026-11-07 令）:
- 工作日 09:00-12:00 / 14:00-18:00 = 全价高峰：只准跑脚本任务(command)，管家任务(agentTurn)/heartbeat 一律暂停
- 12:00-14:00、18:00-次日09:00、周六日、法定节假日 = 半价：全部恢复
- 只暂停/恢复"本方自行暂停"的任务，账本对账；不碰 backup-quiet 已暂停的
用法: peak-token-governor.py {auto|status|pause|resume} [--dry-run]
"""
import json, os, subprocess, sys, fcntl, datetime

WS="/home/j/.openclaw/workspace"
STATE=WS+"/state/work/peak-governor.json"
LEDGER=WS+"/state/work/peak-governor.jsonl"
LOCK=WS+"/state/work/.peak-governor.lock"
QUIET=WS+"/state/backup-quiet/state.json"

def now(): return datetime.datetime.now()
def ledger(rec):
    rec["ts"]=now().isoformat(timespec="seconds")
    with open(LEDGER,"a",encoding="utf-8") as f:
        f.write(json.dumps(rec,ensure_ascii=False)+"\n"); f.flush(); os.fsync(f.fileno())
def load_state():
    try: return json.load(open(STATE))
    except Exception: return {"paused":[], "window":None}
def save_state(s):
    os.makedirs(os.path.dirname(STATE),exist_ok=True)
    json.dump(s,open(STATE,"w"),ensure_ascii=False,indent=1)

def is_holiday(d):
    for p in (WS+"/state/work/holidays.txt", WS+"/state/work/holidays-2026.txt"):
        if os.path.exists(p):
            try:
                for l in open(p,encoding="utf-8"):
                    if l.strip()[:10]==d.isoformat(): return True
            except Exception: pass
    return False

def phase(t=None):
    force=os.environ.get("PEAK_FORCE")
    if force in ("peak","off"): return force,"(强制测试)"
    t=t or now(); d=t.date()
    if d.weekday()>=5 or is_holiday(d): return "off", "周末/节假日"
    m=t.hour*60+t.minute
    if 540<=m<720: return "peak","工作日高峰 09-12"
    if 840<=m<1080: return "peak","工作日高峰 14-18"
    return "off","半价窗"

def cron_list():
    r=subprocess.run(["openclaw","cron","list","--json"],capture_output=True,text=True,timeout=180,stdin=subprocess.DEVNULL)
    if r.returncode!=0: raise RuntimeError("cron list 失败: %s"%(r.stderr or "")[:200])
    d=json.loads(r.stdout)
    return d.get("jobs") or d.get("items") or d

def cron_set(action,jid):
    r=subprocess.run(["openclaw","cron",action,jid],capture_output=True,text=True,timeout=60,stdin=subprocess.DEVNULL)
    return r.returncode==0

def token_jobs(jobs):
    out=[]
    for j in jobs:
        if not j.get("enabled"): continue
        pay=j.get("payload") or {}
        if pay.get("kind") not in ("agentTurn","heartbeat"): continue
        out.append(j)
    return out

def quiet_paused():
    try:
        d=json.load(open(QUIET)); return set(d.get("paused") or [])
    except Exception: return set()

def main():
    action=sys.argv[1] if len(sys.argv)>1 else "auto"
    dry="--dry-run" in sys.argv
    os.makedirs(os.path.dirname(LOCK),exist_ok=True)
    fh=open(LOCK,"w"); fcntl.flock(fh,fcntl.LOCK_EX)
    ph,why=phase()
    st=load_state()
    if action=="status":
        print("阶段: %s（%s）"%(ph,why)); print("本方已暂停: %d 个"%len(st["paused"])); return
    if action=="auto": action="pause" if ph=="peak" else "resume"
    if action=="pause":
        if ph!="peak":
            print("当前非高峰（%s），不暂停"%why); return
        jobs=cron_list(); targets=token_jobs(jobs)
        active=[j for j in jobs if j.get("enabled")]
        cap=int(len(active)*0.7)
        done=[]
        for j in targets[:cap]:
            jid=j.get("id") or j.get("jobId")
            if jid in st["paused"]: continue
            if dry: print("[dry] pause",j.get("name")); continue
            if cron_set("disable",jid):
                st["paused"].append(jid); save_state(st)
                ledger({"action":"pause","id":jid,"name":j.get("name")})
                done.append(j.get("name"))
        st["window"]=why; save_state(st)
        print("高峰暂停 %d 个管家任务（%s）"%(len(done),why))
    else:
        ids=list(st["paused"])
        if not ids: print("没有需要恢复的任务"); return
        qp=quiet_paused(); keep=[]
        for jid in ids:
            if jid in qp:
                ledger({"action":"skip","id":jid,"reason":"backup-quiet仍暂停"}); keep.append(jid); continue
            if dry: print("[dry] enable",jid); keep.append(jid); continue
            if cron_set("enable",jid):
                ledger({"action":"resume","id":jid})
            else:
                keep.append(jid)
        st["paused"]=keep; save_state(st)
        print("恢复 %d 个，仍在暂停 %d 个"%(len(ids)-len(keep),len(keep)))

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("ERR",e); sys.exit(1)
    finally:
        try: fcntl.flock(fh,fcntl.LOCK_UN)
        except Exception: pass
