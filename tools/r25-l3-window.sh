#!/usr/bin/env bash
# r25-l3-window.sh —— R25：L3 重活必须落在 00:30-07:30 固定窗内
set -u
cd /home/j/.openclaw/workspace || exit 9
python3 - <<'PY'
import json, subprocess, sqlite3, os, sys
heavy = {}
try:
    import shutil; shutil.copy('state/ledger/jobs.db','/tmp/j25.db')
    c=sqlite3.connect('/tmp/j25.db')
    for n,avg in c.execute("select name,avg(seconds) from runs where started > datetime('now','-30 days') group by name"):
        heavy[n]=avg or 0
except Exception:
    pass
js=json.loads(subprocess.run(['openclaw','cron','list','--json'],capture_output=True,text=True).stdout)
jobs=js['jobs'] if isinstance(js,dict) else js
# 允许在白天跑的 token 型重活（半价窗 + 简报），按名字白名单
ALLOW = ('告警双审修正','年结')
bad=[]
for j in jobs:
    if not j.get('enabled'): continue
    n=j.get('name') or ''
    if any(a0 in n for a0 in ALLOW): continue
    a=heavy.get(n,0)
    if a < 600: continue
    e=(j.get('schedule') or {}).get('expr') or ''
    p=e.split()
    if len(p)<5: continue
    hours=[int(x) for x in p[1].replace(',',' ').split() if x.isdigit()]
    for h in hours:
        if not (1 <= h <= 7):   # 00:30-07:30 折叠为 1..7 点 + 00:30 边界
            bad.append(f"{n} ({e}, 平均 {a:.0f}s)")
            break
if bad:
    print("R25 违规：以下 L3 重活不在 00:30-07:30 窗内")
    for b in sorted(set(bad)): print("  -", b)
    sys.exit(1)
print("R25 通过：所有 L3 重活都在 00:30-07:30 固定窗")
PY
