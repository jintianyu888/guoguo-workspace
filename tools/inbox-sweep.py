#!/usr/bin/env python3
"""主理人收件箱积压检查：列出 inbox/ 未处理件（未移入 _done/），按龄排序。
用法: inbox-sweep.py [--max-age 分钟]
退出码: 0 无积压 / 1 有超过阈值的积压"""
import os, sys, time, json
WS='/home/j/.openclaw/workspace'
IN=os.path.join(WS,'inbox')
thr=int(sys.argv[sys.argv.index('--max-age')+1]) if '--max-age' in sys.argv else 45
now=time.time(); rows=[]
for f in sorted(os.listdir(IN)):
    p=os.path.join(IN,f)
    if not (os.path.isfile(p) and f.endswith('.md')): continue
    age=int((now-os.path.getmtime(p))/60)
    try: first=open(p,encoding='utf-8').readline().strip()[:40]
    except Exception: first=''
    rows.append((age,f,first))
rows.sort(reverse=True)
late=[r for r in rows if r[0]>=thr]
print('未处理 %d 件，超 %d 分钟 %d 件'%(len(rows), thr, len(late)))
for age,f,first in rows[:8]: print('  %4d 分钟 %s'%(age,f))
if late:
    print('积压：'+ '、'.join('%s(%d分钟)'%(f,age) for age,f,_ in late[:3]))
    sys.exit(1)
sys.exit(0)