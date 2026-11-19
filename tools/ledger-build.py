#!/usr/bin/env python3
# ledger-build.py —— 唯一账本构建器（只读扫描，不改任何现有台账）
# 生成 state/ledger/ledger.db：scripts / cron_jobs / links / runs 四张表 + 对账报告
import os,sqlite3,json,subprocess,re,time,glob,sys
W='/home/j/.openclaw/workspace'
DB=W+'/state/ledger/ledger.db'
os.makedirs(os.path.dirname(DB),exist_ok=True)
c=sqlite3.connect(DB)
c.executescript('''
create table if not exists scripts(path text primary key, kind text, purpose text, bytes int, mtime int, registered int default 1);
create table if not exists cron_jobs(job_id text primary key, name text, expr text, script_path text, payload_kind text, enabled int);
create table if not exists tasks(task_id text primary key, title text, status text, assignee text, verify_cmd text);
create table if not exists runs(run_id integer primary key autoincrement, script_path text, job_id text, started_at int, ended_at int, rc int, note text);
''')
def purpose(p):
    try:
        with open(p,errors='ignore') as f:
            head=[next(f) for _ in range(6)]
        for l in head:
            l=l.strip()
            if l.startswith('#') and len(l)>4 and 'usr/bin' not in l and 'coding' not in l:
                return l.lstrip('# ').strip()[:120]
    except Exception: pass
    return ''
n=0
for pat in ('tools/*.sh','tools/*.py'):
    for p in glob.glob(os.path.join(W,pat)):
        st=os.stat(p); n+=1
        c.execute('insert or replace into scripts(path,kind,purpose,bytes,mtime) values(?,?,?,?,?)',
                  (p.replace(W+'/',''), os.path.splitext(p)[1], purpose(p), st.st_size, int(st.st_mtime)))
out=subprocess.run(['openclaw','cron','list','--json'],capture_output=True,text=True,cwd='/home/j/.openclaw').stdout
d=json.loads(out); jobs=d.get('jobs',d) if isinstance(d,dict) else d
m=0
for j in jobs:
    pl=j.get('payload') or {}
    argv=pl.get('argv') or []
    s=''
    for a in argv:
        if isinstance(a,str) and ('tools/' in a) and (a.endswith('.sh') or a.endswith('.py')):
            s=a.replace('/home/j/.openclaw/workspace/',''); break
    sch=j.get('schedule') or {}
    c.execute('insert or replace into cron_jobs(job_id,name,expr,script_path,payload_kind,enabled) values(?,?,?,?,?,?)',
              (j['id'], j.get('name'), sch.get('expr',''), s, pl.get('kind',''), 1 if j.get('enabled') else 0))
    m+=1
t=sqlite3.connect(W+'/state/tasks/tasks.db')
try:
    cols=[r[1] for r in t.execute('pragma table_info(tasks)')]
    print('tasks.db 列:',cols[:12])
except Exception as e: print('tasks err',e)
c.commit()
print('scripts:',n,'cron:',m)
