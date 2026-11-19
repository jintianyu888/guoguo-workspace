#!/usr/bin/env python3
# 2026-10-28: 采集各 agent 最近调用过的工具（只读 sqlite 转录，nested-tool 事件）
import sqlite3, glob, os, time, json
now = time.time()
out = []
for p in glob.glob('/home/j/.openclaw/agents/*/agent/openclaw-agent.sqlite'):
    try:
        if now - os.path.getmtime(p) > 900: continue
    except OSError: continue
    name = p.split('/')[5]
    try:
        c = sqlite3.connect('file:' + p + '?mode=ro', uri=True, timeout=1.5)
        rows = list(c.execute('select seq, event_json, created_at from transcript_events where event_json is not null order by seq desc limit 250'))
    except Exception:
        continue
    for seq, ej, ca in rows:
        if 'nested-tool' not in ej and '"toolName"' not in ej: continue
        try: d = json.loads(ej)
        except Exception: continue
        m = d.get('message') or {}
        det = m.get('details') or {}
        if not isinstance(det, dict): continue
        nm = det.get('toolName')
        if not nm: continue
        t = det.get('startedAt') or det.get('timestamp') or ca
        try: t_ms = int(t)
        except Exception: t_ms = int(ca or 0)
        if t_ms < 1e12: t_ms = int(ca or 0)
        age = now - t_ms / 1000
        if age > 600: continue
        out.append({'agent': name, 'tool': str(nm), 'at': t_ms, 'ageMs': int(age * 1000)})
seen = set(); res = []
for x in sorted(out, key=lambda z: z['at'], reverse=True):
    k = (x['agent'], x['tool'])
    if k in seen: continue
    seen.add(k); res.append(x)
print(json.dumps(res[:16], ensure_ascii=False))