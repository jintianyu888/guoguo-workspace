#!/bin/bash
# bg-status.sh —— 后台任务一览（2026-10-17 主公要求恢复可见性）
set -u
W=/home/j/.openclaw/workspace
echo "== 正在运行的长任务 =="
ps -eo pid,etime,pcpu,cmd --sort=-pcpu 2>/dev/null | grep -E "rsync |wsl.exe|wsl-export|backup|tar -c" | grep -v grep | head -6 | while read -r pid et pc cmd; do
  echo "  PID $pid 已跑 $et CPU $pc% $(echo "$cmd" | cut -c1-90)"
done
echo "== 最近任务日志（START/DONE）=="
for f in $(ls -t "$W"/state/work/*.log "$W"/state/*.log 2>/dev/null | head -8); do
  s=$(grep -c "START" "$f" 2>/dev/null)
  d=$(grep -c "DONE\|完成\|rc=0" "$f" 2>/dev/null)
  last=$(tail -1 "$f" 2>/dev/null | cut -c1-70)
  echo "  $(basename "$f"): START=$s DONE=$d 尾行: $last"
done
echo "== 即将运行的定时任务 =="
openclaw cron list --json 2>/dev/null | python3 -c "
import sys,json,datetime
d=json.load(sys.stdin); jobs=d.get('jobs',d) if isinstance(d,dict) else d
rows=[]
for j in jobs:
    ms=(j.get('state') or {}).get('nextRunAtMs') or 0
    if ms>0 and j.get('enabled') is not False: rows.append((ms,j.get('name')))
rows.sort()
for ms,name in rows[:6]:
    print('  %s  %s' % (datetime.datetime.fromtimestamp(ms/1000).strftime('%m-%d %H:%M'), name))
" 2>/dev/null
