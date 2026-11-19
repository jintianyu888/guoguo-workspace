#!/usr/bin/env python3
# accept-selfreview.py v1.0 (2026-11-19) —— 13:45 一次性验收：五家自审结论是否都落盘
import os, datetime, subprocess
W = '/home/j/.openclaw/workspace'
WS = {'maint': '/home/j/openclaw-workspaces/maint', 'backup': '/home/j/.openclaw/workspace-backup',
      'model': '/home/j/.openclaw/workspace-model', 'work': '/home/j/openclaw-workspaces/work',
      'hermess': '/home/j/openclaw-workspaces/sheet-music'}
day = datetime.date.today().isoformat()
ok, miss = [], []
for a, ws in WS.items():
    p = os.path.join(ws, 'state/self-review/self-review-%s.md' % day)
    t = open(p, errors='replace').read() if os.path.exists(p) else ''
    (ok if '## 结论' in t else miss).append(a)
msg = '自审收割验收 %s：%d/5 有结论' % (day, len(ok))
if miss:
    msg += '；仍缺：' + '、'.join(miss)
print(msg)
subprocess.run(['bash', W + '/tools/notify.sh', '--digest', msg], timeout=120)
raise SystemExit(0 if not miss else 1)
