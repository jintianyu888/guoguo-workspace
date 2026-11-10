#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ledger-verify.py —— 账本验证器：用真实检查代替记忆
用法: ledger-verify.py [--apply]
"""
import json,os,subprocess,sys,time,re

WS='/home/j/.openclaw/workspace'
LED=os.path.join(WS,'state/tasks/tasks.json')

def sh(cmd,timeout=30):
    try:
        r=subprocess.run(cmd,shell=True,cwd=WS,capture_output=True,text=True,timeout=timeout)
        return (r.stdout or '').strip()
    except Exception as e:
        return 'ERR:'+str(e)[:40]

def check_166():
    out=sh("grep -c 'tools/stab_report.py' tools/stability-check.sh")
    rel=sh("grep -c '^python3 tools/stab_report.py\|; python3 tools/stab_report.py' tools/stability-check.sh")
    return rel.strip()=='0', '相对调用次数='+rel

def check_173():
    out=sh("grep -cE 'dual_channel|gpu_pct|GPU 占比' tools/stability-check.sh")
    return out not in ('','0'), '命中='+out

def check_46():
    out=sh("test -x /home/j/.openclaw/venvs/demucs/bin/python && echo YES || echo NO")
    return out=='YES', out

def check_url(url):
    def f():
        out=sh("curl -s -o /dev/null -w '%{http_code}' --max-time 5 "+url)
        return out=='200', 'http='+out
    return f

def check_150():
    out=sh("ls -d /home/j/.openclaw/workspace-* 2>/dev/null | wc -l")
    return out.strip()=='0', '旧副本数='+out

def check_186():
    pid=sh("systemctl --user show -p MainPID --value openclaw-gateway").strip()
    out=sh("ps -o rss= -p "+pid).strip()
    try: gb=int(out)/1048576
    except Exception: return False,'读取失败'
    return gb<6.0, 'RSS=%.2fGB'%gb

CHECKS={
 166:('stability-check 改绝对路径调 stab_report',check_166),
 173:('stability-check 已加三项检查',check_173),
 46:('demucs venv 就绪',check_46),
 124:('/health 返回 200',check_url("http://127.0.0.1:18789/health")),
 172:('看板服务返回 200',check_url("http://127.0.0.1:18810/")),
 150:('旧工作区副本已清',check_150),
 186:('网关 RSS < 6GB',check_186),
}

def main():
    apply_mode='--apply' in sys.argv
    d=json.load(open(LED,encoding='utf-8'))
    idx={i.get('no'):i for i in d['items'] if isinstance(i,dict)}
    closed=[]
    print('== 验证结果 ==')
    for no,(desc,fn) in CHECKS.items():
        it=idx.get(no)
        if not it or it.get('status') in ('done','cancelled'): continue
        try: ok,ev=fn()
        except Exception as e: ok,ev=False,'ERR '+str(e)[:30]
        print('#%s %s -> %s [%s]'%(no,desc,ev,'通过' if ok else '未通过'))
        if ok and apply_mode:
            now=time.strftime('%Y-%m-%dT%H:%M:%S+08:00')
            n=it.get('notes'); n=' ｜ '.join(map(str,n)) if isinstance(n,list) else str(n or '')
            it['notes']=n+'｜'+now+' 验证器通过自动关闭（%s）'%ev
            it['status']='done'; it['updated']=now; it['closed_by']='verifier'
            closed.append(no)
    if apply_mode and closed:
        # 统一走 SQLite 账本，再导出视图
        for no in closed:
            subprocess.run(['python3','tools/tasks-db.py','done',str(no),'--by','verifier','--why','验证器通过'],
                           cwd=WS,capture_output=True,text=True)
        subprocess.run(['python3','tools/tasks-db.py','export'],cwd=WS,capture_output=True,text=True)
    if apply_mode: print('自动关闭:',closed or '无')

if __name__=='__main__': main()
