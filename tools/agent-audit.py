#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent-audit.py — 管家用量/职责/空转 体检（零 token）
用法: python3 tools/agent-audit.py [--json] [--days 7]
输出: Markdown 表 + 摘要；同时写 state/work/agent-audit.json
"""
import os, sys, json, time, shutil, sqlite3, re, tempfile, datetime

CFG = '/home/j/.openclaw/openclaw.json'
STATE = '/home/j/.openclaw/workspace/state/work'
DAYS = 7
for i, a in enumerate(sys.argv):
    if a == '--days' and i + 1 < len(sys.argv):
        DAYS = int(sys.argv[i + 1])

def agents():
    d = json.load(open(CFG))
    e = d.get('agents', {}).get('entries', {})
    items = e.items() if isinstance(e, dict) else [(x.get('id'), x) for x in e]
    out = []
    for k, v in items:
        w = (v or {}).get('workspace') or ''
        if w.startswith('/home/j/openclaw-workspaces/'):
            out.append((k, w))
    return sorted(out)

def duty_info(ws):
    p = os.path.join(ws, 'AGENTS.md')
    if not os.path.exists(p):
        return {'agents_md': False, 'size': 0, 'has_duty': False, 'role': ''}
    txt = open(p, encoding='utf-8', errors='ignore').read()
    txt2 = re.sub(r'<!-- NEW-SESSION-RULE.*?<!-- /NEW-SESSION-RULE:v1 -->', '', txt, flags=re.S)
    lines = [l.strip() for l in txt2.splitlines() if l.strip()]
    has = any(l.startswith('##') and '职责' in l for l in lines)
    role = ''
    k = next((n for n, l in enumerate(lines) if l.startswith('## 角色')), None)
    if k is not None:
        role = ' '.join(re.sub(r'^[-*]\s*', '', x) for x in lines[k + 1:k + 3])
    if not role:
        role = next((l for l in lines if not l.startswith('#')), '')[:120]
    return {'agents_md': True, 'size': len(txt), 'has_duty': has, 'role': role[:200]}

def usage(sid, days):
    src = f'/home/j/.openclaw/agents/{sid}/agent/openclaw-agent.sqlite'
    if not os.path.exists(src):
        return {'db': False}
    tmp = os.path.join(tempfile.gettempdir(), f'audit-{sid}.sqlite')
    try:
        shutil.copy(src, tmp)
        c = sqlite3.connect(tmp)
        now = time.time() * 1000
        since = now - days * 86400 * 1000
        tot = c.execute('select count(*) from transcript_events').fetchone()[0]
        ev = c.execute('select count(*) from transcript_events where created_at>=?', (since,)).fetchone()[0]
        usr = c.execute("select count(*) from transcript_events where created_at>=? and message_role='user'", (since,)).fetchone()[0]
        last = c.execute('select max(created_at) from transcript_events').fetchone()[0] or 0
        rows = list(c.execute("select status,count(*) from session_nodes group by status"))
        st = {r[0]: r[1] for r in rows}
        c.close(); os.unlink(tmp)
        return {'db': True, 'events': tot, 'events_window': ev, 'user_window': usr,
                'last': last, 'sessions': st}
    except Exception as ex:
        return {'db': False, 'error': str(ex)}

def main():
    rows = []
    for sid, ws in agents():
        d = duty_info(ws)
        u = usage(sid, DAYS)
        last = u.get('last') or 0
        rows.append({
            'id': sid, 'workspace': ws, 'agents_md': d['agents_md'], 'agents_size': d['size'],
            'has_duty': d['has_duty'], 'role': d['role'],
            'events': u.get('events', 0), 'events_window': u.get('events_window', 0),
            'user_window': u.get('user_window', 0),
            'last': datetime.datetime.fromtimestamp(last / 1000).strftime('%Y-%m-%d %H:%M') if last else '',
            'last_ms': last, 'sessions': u.get('sessions', {}), 'error': u.get('error', ''),
        })
    # 角色重复检测
    seen = {}
    for r in rows:
        key = re.sub(r'\s+', '', r['role'])[:60]
        if len(key) > 15:
            seen.setdefault(key, []).append(r['id'])
    dups = [v for v in seen.values() if len(v) > 1]
    for r in rows:
        r['idle_days'] = round((time.time() * 1000 - r['last_ms']) / 86400000, 1) if r['last_ms'] else None

    if '--json' in sys.argv:
        print(json.dumps({'generated': datetime.datetime.now().isoformat(timespec='seconds'),
                          'days': DAYS, 'agents': rows, 'dup_roles': dups}, ensure_ascii=False, indent=1))
    else:
        print(f"# 管家体检（近 {DAYS} 天）\n")
        print('| 管家 | 事件 | 窗内事件 | 窗内提问 | 最后活动 | 闲置天 | 职责节 | 失败/中止 |')
        print('|---|---|---|---|---|---|---|---|')
        for r in rows:
            fails = sum(v for k, v in r['sessions'].items() if k in ('failed', 'aborted'))
            print(f"| {r['id']} | {r['events']} | {r['events_window']} | {r['user_window']} | {r['last'] or '-'} | {r['idle_days'] if r['idle_days'] is not None else '-'} | {'Y' if r['has_duty'] else '**N**'} | {fails or 0} |")
        print('\n## 空转（近 %d 天零交互）' % DAYS)
        print(', '.join(r['id'] for r in rows if r['events_window'] == 0) or '无')
        print('\n## 角色描述重复')
        print('\n'.join(' / '.join(v) for v in dups) or '无')
        print('\n## 缺职责范围节')
        print(', '.join(r['id'] for r in rows if not r['has_duty']) or '无')

    os.makedirs(STATE, exist_ok=True)
    json.dump({'generated': datetime.datetime.now().isoformat(timespec='seconds'), 'days': DAYS,
               'agents': rows, 'dup_roles': dups},
              open(os.path.join(STATE, 'agent-audit.json'), 'w'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
