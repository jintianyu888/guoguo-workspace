#!/usr/bin/env bash
set -uo pipefail
W=/home/j/.openclaw/workspace
cp "$W/state/tasks/tasks.db" /tmp/r38.db 2>/dev/null
python3 - <<'PY'
import json,sqlite3,os,datetime
c=sqlite3.connect('/tmp/r38.db')
cut=(datetime.date.today()-datetime.timedelta(days=7)).isoformat()
rows=[(r[0],r[1],(r[2] or '')) for r in c.execute("select no,title,verify from tasks where status='done' and substr(updated,1,10)>=?",(cut,))]
log='/home/j/.openclaw/workspace/state/verify/third-eye.jsonl'
seen=set(); human=set()
if os.path.exists(log):
    for l in open(log,encoding='utf-8'):
        try: r=json.loads(l)
        except Exception: continue
        if r.get('rc')==0 or r.get('verdict')=='通过':
            seen.add(str(r.get('task')))
            if r.get('kind')=='human': human.add(str(r.get('task')))
miss=[]
for n,t,v in rows:
    s=str(n)
    if s in seen: continue
    miss.append((n,t,v[:40]))
print('近7天收口 %d 条，有第三视角 %d 条，缺 %d 条'%(len(rows),len(rows)-len(miss),len(miss)))
for n,t,v in miss[:10]: print('  ✗ #%s %s'%(n,(t or '')[:40]))
if miss:
    print('补：python3 tools/third-eye.py record --task <no> --cmd "<命令>" 或 ack --task <no> --by owner')
    raise SystemExit(1)
print('GREEN 全部有第三视角记录')
PY
