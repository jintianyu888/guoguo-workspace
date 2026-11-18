#!/usr/bin/env python3
# alert-digest-add.py v1.0 (2026-11-18) —— 把 P1 告警塞进当日汇总队列（同指纹当天只留一条）
import json, os, sys, datetime

WS = '/home/j/.openclaw/workspace'
Q = WS + '/state/alerts/digest.jsonl'
os.makedirs(os.path.dirname(Q), exist_ok=True)
key, msg = sys.argv[1], sys.argv[2]
today = datetime.date.today().isoformat()
seen = set()
if os.path.exists(Q):
    for line in open(Q):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if (r.get('ts') or '')[:10] == today:
            seen.add(r.get('key'))
if key in seen:
    sys.exit(0)
with open(Q, 'a') as f:
    f.write(json.dumps({'ts': datetime.datetime.now().isoformat(timespec='seconds'), 'key': key, 'text': msg}, ensure_ascii=False) + '\n')
print('queued', key)
