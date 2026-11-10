#!/usr/bin/env bash
# agent-usage.sh v2 —— 各管家用量台账（占用空间 + 会话数 + 活跃度事件数）
W=/home/j/.openclaw; A=$W/agents
echo "📊 各管家用量台账 · $(date '+%F %H:%M')"
printf '%-16s %8s %6s %9s\n' '管家' '占用' '会话' '活跃度'
python3 - << 'PY'
import sqlite3, glob, os, subprocess
W='/home/j/.openclaw'
def events(a):
    db=f'{W}/agents/{a}/agent/openclaw-agent.sqlite'
    try:
        c=sqlite3.connect(db); n=list(c.execute('select count(*) from transcript_events'))[0][0]; c.close(); return n
    except Exception: return 0
rows=[]
for d in sorted(glob.glob(f'{W}/workspace*')):
    n=os.path.basename(d); name=n.replace('workspace-','') if n!='workspace' else 'main'
    sz=subprocess.run(['du','-sh',d],capture_output=True,text=True).stdout.split()[0] if os.path.isdir(d) else '?'
    sc=len(glob.glob(f'{W}/agents/{name}/**/*', recursive=True))
    rows.append((name, sz, sc, events(name)))
rows.sort(key=lambda x: x[3], reverse=True)
for name,sz,sc,ev in rows:
    print(f'{name:<16} {sz:>8} {sc:>6} {ev:>9}')
PY
echo '【全局】'$(openclaw status --usage 2>/dev/null | grep -oE 'Balance \\$[0-9.]+' | head -1)
