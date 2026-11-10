#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tasks-db.py —— 统一任务账本（SQLite 为唯一真源，tasks.json 仅作导出视图）
用法:
  tasks-db.py import        从 tasks.json 首次导入（含归档）
  tasks-db.py export        导出 tasks.json（供日报/页脚等老脚本读取）
  tasks-db.py list [--all]  列出任务
  tasks-db.py done <no> --by owner|agent|verifier --why "..."   
  tasks-db.py set <no> status=xxx prio=N verify="cmd"
  tasks-db.py log [no]      查看变更审计
  tasks-db.py check         一致性自检（库 vs 视图）
"""
import sqlite3,json,os,sys,time,glob

WS='/home/j/.openclaw/workspace'
DB=os.path.join(WS,'state/tasks/tasks.db')
JSON=os.path.join(WS,'state/tasks/tasks.json')
ARC=os.path.join(WS,'state/tasks/archive')

SCHEMA='''
CREATE TABLE IF NOT EXISTS tasks(
  no INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending','open','in_progress','paused','quarantine','done','cancelled')),
  kind TEXT, grp TEXT, prio INTEGER, notes TEXT,
  verify TEXT, created TEXT, updated TEXT, closed_by TEXT
);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, no INTEGER, field TEXT, old TEXT, new TEXT,
  actor TEXT, reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_events_no ON events(no);
'''

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA foreign_keys=ON')
    c.executescript(SCHEMA); return c

def now(): return time.strftime('%Y-%m-%dT%H:%M:%S+08:00')

def cmd_import():
    c=conn(); n=0
    src=[JSON]+sorted(glob.glob(os.path.join(ARC,'*.json')))
    seen=set()
    for p in src:
        if not os.path.exists(p): continue
        try: d=json.load(open(p,encoding='utf-8'))
        except Exception: continue
        items=d.get('items') if isinstance(d,dict) else d
        if not isinstance(items,list): continue
        for i in items:
            if not isinstance(i,dict): continue
            try: no=int(i.get('no'))
            except Exception: continue
            if no in seen: continue
            seen.add(no)
            st=i.get('status') if i.get('status') in ('pending','open','in_progress','paused','quarantine','done','cancelled') else 'pending'
            nts=i.get('notes'); nts=' ｜ '.join(map(str,nts)) if isinstance(nts,list) else str(nts or '')
            c.execute('INSERT OR REPLACE INTO tasks(no,title,status,kind,grp,prio,notes,verify,created,updated,closed_by) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (no,str(i.get('title') or '(无标题)'),st,i.get('kind'),i.get('group'),
                 i.get('prio') or i.get('priority'),nts,i.get('verify'),
                 str(i.get('created') or '')[:19],str(i.get('updated') or now())[:19],i.get('closed_by')))
            c.execute('INSERT INTO events(ts,no,field,old,new,actor,reason) VALUES(?,?,?,?,?,?,?)',
                (now(),no,'import','','' + st,'migrate','首次迁入 SQLite'))
            n+=1
    c.commit(); print('导入',n,'条 →',DB)

def cmd_export():
    c=conn()
    rows=[dict(r) for r in c.execute('SELECT * FROM tasks ORDER BY no')]
    items=[]
    for r in rows:
        items.append({'no':r['no'],'title':r['title'],'status':r['status'],'kind':r['kind'],
                      'group':r['grp'],'prio':r['prio'],'notes':r['notes'],
                      'updated':r['updated'],'closed_by':r['closed_by'],
                      'created': r['created'] if 'created' in r.keys() else '',
                      # 2026-11-08 修：导出缺 owner → 页脚把主公待拍板全算成「果果待办」
                      'owner': '主公' if (r['wait_user'] if 'wait_user' in r.keys() else 0) else '果果',
                      'wait_user': r['wait_user'] if 'wait_user' in r.keys() else 0,
                      'due_plan': r['due_plan'] if 'due_plan' in r.keys() else '',
                      'eta_min': r['eta_min'] if 'eta_min' in r.keys() else 0,
                      'slip_reason': r['slip_reason'] if 'slip_reason' in r.keys() else ''})
    out={'updated':now(),'source':'tasks.db','items':items}
    tmp=JSON+'.tmp'
    json.dump(out,open(tmp,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    os.replace(tmp,JSON)
    print('导出视图',len(items),'条 →',JSON)

def cmd_list(args):
    c=conn(); show_all='--all' in args
    q='SELECT no,status,grp,prio,title FROM tasks'
    if not show_all: q+=" WHERE status NOT IN ('done','cancelled')"
    q+=' ORDER BY (prio IS NULL), prio, no'
    for r in c.execute(q):
        print('#%-4s [%-11s] %-8s %s'%(r['no'],r['status'],r['grp'] or '-',(r['title'] or '')[:52]))

def cmd_done(args):
    no=int(args[0]); by='agent'; why=''
    for i,a in enumerate(args):
        if a=='--by': by=args[i+1]
        if a=='--why': why=args[i+1]
    nxt=''
    for i,a in enumerate(args):
        if a=='--next': nxt=args[i+1]
    c=conn(); r=c.execute('SELECT status FROM tasks WHERE no=?',(no,)).fetchone()
    if not r: print('无此任务'); return 2
    old=r['status']
    # --- 关闭关卡：有 verify 的任务必须先跑通验收，不许自报完成（双审 2026-10-28）---
    vrow=c.execute('SELECT verify,title FROM tasks WHERE no=?',(no,)).fetchone()
    vcmd=(vrow['verify'] if vrow else '') or ''
    force=('--force' in args)
    if force and not why:
        print('--force 必须同时给 --why "为什么跳验收"，否则不许跳')
        return 3
    if (not vcmd) and by!='owner' and not force:
        c.execute('INSERT INTO events(ts,no,field,old,new,actor,reason) VALUES(?,?,?,?,?,?,?)',
                  (now(),no,'verify','missing','reject','agent','无验收命令，拒绝自报完成'))
        c.commit()
        print('拒绝关闭 #%s：没有验收命令，不许自报完成'%no)
        print('  二选一：1) 先定验收 python3 tools/tasks-db.py set %d verify="<命令>"  2) --force --why "为什么无法机器验收"'%no)
        return 3
    if vcmd and (force or by=='owner'):
        c.execute('INSERT INTO events(ts,no,field,old,new,actor,reason) VALUES(?,?,?,?,?,?,?)',
                  (now(),no,'verify','skipped','forced',by,'跳过验收：'+('-force' if force else 'owner 关闭')))
    if vcmd and by!='owner' and not force:
        import subprocess
        try:
            pr=subprocess.run(vcmd,shell=True,cwd='/home/j/.openclaw/workspace',
                              capture_output=True,text=True,timeout=90)
            ok=(pr.returncode==0); out=((pr.stdout or '')+(pr.stderr or '')).strip()
            rcv=pr.returncode
        except Exception as ex:
            ok=False; out='verify 运行异常: %s'%ex; rcv=-1
        if not ok:
            c.execute('INSERT INTO events(ts,no,field,old,new,actor,reason) VALUES(?,?,?,?,?,?,?)',
                      (now(),no,'verify','fail','reject','agent',('验收未过 rc=%s: %s'%(rcv,out))[:300]))
            c.commit()
            print('拒绝关闭 #%s：验收命令未通过（rc=%s）'%(no,rcv))
            print('  命令: %s'%vcmd)
            print('  输出: %s'%(out[:400] or '(无输出)'))
            print('  如确系误判，用 --force 或 --by owner 复跑')
            return 3
        c.execute('INSERT INTO events(ts,no,field,old,new,actor,reason) VALUES(?,?,?,?,?,?,?)',
                  (now(),no,'verify','pending','pass','agent','验收通过 rc=0'))
    c.execute("UPDATE tasks SET status='done',updated=?,closed_by=? WHERE no=?",(now(),by,no))
    c.execute('INSERT INTO events(ts,no,field,old,new,actor,reason) VALUES(?,?,?,?,?,?,?)',(now(),no,'status',old,'done',by,why))
    c.commit()
    # 完成即报：已完成什么 + 下一步（主公 2026-11-07 13:55 令）；--no-notify 可跳过
    if '--no-notify' not in args:
        import subprocess as _sp
        _did = why or ('已按验收标准关闭' if vcmd else '已完成')
        try:
            _sp.run(['bash','/home/j/.openclaw/workspace/tools/completion-notify.sh','--no',str(no),
                     '--did',_did,'--next',nxt or '继续推进在办任务','--by',by],
                    capture_output=True,text=True,timeout=25)
        except Exception:
            pass
    # 提前完成 → 后续计划自动前移（2026-11-07 主公令）
    if '--no-reflow' not in sys.argv:
        try:
            _sp.run(['python3','/home/j/.openclaw/workspace/tools/plan-reflow.py'],
                    capture_output=True,text=True,timeout=30)
        except Exception:
            pass
    print('#%s %s → done（by %s）'%(no,old,by))

def cmd_set(args):
    no=int(args[0]); c=conn()
    r=c.execute('SELECT status FROM tasks WHERE no=?',(no,)).fetchone()
    if not r: print('无此任务'); return 2
    for kv in args[1:]:
        if '=' not in kv: continue
        k,v=kv.split('=',1)
        col={'status':'status','prio':'prio','verify':'verify','note':'notes','group':'grp',
             'due_plan':'due_plan','eta_min':'eta_min','wait_user':'wait_user','agent':'agent',
             'slip_reason':'slip_reason','pin_time':'pin_time','blocked':'blocked'}.get(k)
        if not col: continue
        if k=='note':
            cur=c.execute('SELECT notes FROM tasks WHERE no=?',(no,)).fetchone()['notes'] or ''
            v=cur+'｜'+now()+' '+v
        c.execute('UPDATE tasks SET %s=?,updated=? WHERE no=?'%col,(v,now(),no))
        c.execute('INSERT INTO events(ts,no,field,old,new,actor,reason) VALUES(?,?,?,?,?,?,?)',(now(),no,k,'',str(v),'agent','set'))
    c.commit(); print('#%s 已更新'%no)


def cmd_add(args):
    # add <no> <title> [key=value ...]  key: status/group/prio/kind/verify/note
    no=int(args[0]); title=args[1]
    if '--force' not in args:
        import subprocess as _sp
        try:
            _d=_sp.run(['python3','/home/j/.openclaw/workspace/tools/plan-guard.py','--dup',title],
                       capture_output=True,text=True,timeout=30)
            if _d.returncode==6:
                print((_d.stdout or '').strip()); print('查重命中：先合并到现有条目，确需新建加 --force')
                return 6
        except Exception:
            pass
    kv={'status':'pending','grp':None,'prio':None,'kind':'task','verify':None,'note':''}
    for a in args[2:]:
        if '=' in a:
            k,val=a.split('=',1)
            k={'status':'status','group':'grp','grp':'grp','prio':'prio','kind':'kind','verify':'verify','note':'note','notes':'note'}[k]
            kv[k]=val
    c=conn(); nows=now()
    c.execute('INSERT OR REPLACE INTO tasks(no,title,status,kind,grp,prio,notes,verify,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',
        (no,title,kv['status'],kv['kind'],kv['grp'],int(kv['prio']) if kv['prio'] else None,
         (kv['note'] or '')+'｜'+nows+' 建条（主公 10-28 十三条指示拆解）',kv['verify'],nows,nows))
    c.execute('INSERT INTO events(ts,no,field,old,new,actor,reason) VALUES(?,?,?,?,?,?,?)',
        (nows,no,'create','','pending','agent','主公 2026-10-28 10:50 指示拆解'))
    c.commit(); print('+#%s %s [%s/prio %s]'%(no,title,kv['status'],kv['prio'] or '-'))

def cmd_log(args):
    c=conn()
    q='SELECT ts,no,field,old,new,actor,reason FROM events'
    p=[]
    if args: q+=' WHERE no=?'; p=[int(args[0])]
    q+=' ORDER BY id DESC LIMIT 30'
    for r in c.execute(q,p):
        print('%s #%s %s %s→%s by %s %s'%(r['ts'][:19],r['no'],r['field'],r['old'],r['new'],r['actor'],(r['reason'] or '')[:30]))

def cmd_check():
    c=conn()
    n=c.execute('SELECT COUNT(*) c FROM tasks').fetchone()['c']
    live=c.execute("SELECT COUNT(*) c FROM tasks WHERE status NOT IN ('done','cancelled')").fetchone()['c']
    ev=c.execute('SELECT COUNT(*) c FROM events').fetchone()['c']
    print('库内 %d 条，未结 %d，事件 %d 条'%(n,live,ev))
    if os.path.exists(JSON):
        d=json.load(open(JSON,encoding='utf-8'))
        print('视图 %d 条｜一致=%s'%(len(d.get('items',[])), len(d.get('items',[]))==n))

if __name__=='__main__':
    cmd=sys.argv[1] if len(sys.argv)>1 else 'check'
    a=sys.argv[2:]
    {'import':lambda:cmd_import(),'export':lambda:cmd_export(),'list':lambda:cmd_list(a),
     'done':lambda:cmd_done(a),'set':lambda:cmd_set(a),'add':lambda:cmd_add(a),'log':lambda:cmd_log(a),
     'check':lambda:cmd_check()}.get(cmd,lambda:print('未知命令'))()
