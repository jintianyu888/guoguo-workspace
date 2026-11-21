#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tier-window-check.py —— R22：T1 重活（≥10 分钟或 IO 密集）不得落在主公使用时段 08:00–24:00。
读 cron 列表 + jobs.db 平均耗时；违规即列出并 rc=1。零 token。"""
import json, subprocess, sqlite3, os, sys

W = '/home/j/.openclaw/workspace'
HEAVY_NAMES = ('全量备份','哈希','镜像','恢复演练','T1','T2','杀毒','归档','batch-extract','镜像校验','一致性')
GUARD = ('guard','watchdog','哨兵','保险','sentinel','心跳','heartbeat')
def is_heavy(name, body, avg):
    if any(k in name for k in GUARD): return False
    if avg >= 600: return True
    return avg >= 300 and any(k in (name + body) for k in HEAVY_NAMES)

def main():
    out = subprocess.run(['openclaw','cron','list','--json'], capture_output=True, text=True, timeout=120).stdout
    d = json.loads(out); js = d.get('jobs') or d
    con = sqlite3.connect(os.path.join(W,'state/ledger/jobs.db'))
    bad = []
    for j in js:
        if not j.get('enabled'): continue
        sched = (j.get('schedule') or {}).get('expr','')
        if not sched: continue
        parts = sched.split()
        if len(parts) < 5: continue
        minute, hour = parts[0], parts[1]
        if '/' in hour or ',' in hour or '-' in hour or hour == '*':
            hours = []
            for token in hour.split(','):
                if '-' in token:
                    a,b = token.split('-'); hours += list(range(int(a), int(b)+1))
                elif '/' in token:
                    step = int(token.split('/')[1]); hours += list(range(0,24,step))
                elif token == '*':
                    hours += list(range(0,24))
                else:
                    hours.append(int(token))
        else:
            hours = [int(hour)]
        p = j.get('payload') or {}
        body = str(p.get('argv') or p.get('message') or '')
        r = con.execute("select avg(seconds) from runs where name=? and status='ok'", (j.get('name'),)).fetchone()
        avg = int(r[0] or 0) if r else 0
        if not is_heavy(j.get('name'), body, avg): continue
        for h in hours:
            if 8 <= h < 24:
                bad.append((j.get('name'), sched, avg)); break
    if bad:
        print('R22 违规：T1 重活在 08:00–24:00 触发（%d 项）' % len(bad))
        for n,s,a in bad: print('  - %s %s（均 %d 秒）' % (n, s, a))
        return 1
    print('R22 通过：T1 重活全部落在系统时段')
    return 0

if __name__ == '__main__':
    sys.exit(main())
