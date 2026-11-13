#!/usr/bin/env python3
# activity.py —— 统一"正在干什么"状态，供面板与预警使用（零 token）
import json, os, sys, time, tempfile
from datetime import datetime, timezone

WS = '/home/j/.openclaw/workspace'
D = os.path.join(WS, 'state', 'status')
F = os.path.join(D, 'activity.json')
L = os.path.join(D, 'activity.log.jsonl')

def now():
    return int(time.time())

def read():
    try:
        with open(F, encoding='utf8') as f:
            return json.load(f)
    except Exception:
        return {'kind': 'idle', 'phase': '正常', 'percent': None, 'updated_at': 0}

def write(obj):
    os.makedirs(D, exist_ok=True)
    obj['updated_at'] = now()
    tmp = F + '.tmp'
    with open(tmp, 'w', encoding='utf8') as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, F)
    with open(L, 'a', encoding='utf8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')
    return obj

def main():
    a = sys.argv[1:]
    if not a:
        print(json.dumps(read(), ensure_ascii=False)); return
    cmd = a[0]
    if cmd == 'get':
        print(json.dumps(read(), ensure_ascii=False))
    elif cmd == 'clear':
        write({'kind': 'idle', 'phase': '正常', 'percent': None, 'note': ''})
        print('cleared')
    elif cmd == 'set':
        kw = {}
        for x in a[1:]:
            if '=' in x:
                k, v = x.split('=', 1); kw[k] = v
        kind = kw.get('kind', 'task')
        obj = read()
        obj.update({
            'kind': kind,
            'phase': kw.get('phase', obj.get('phase', '进行中')),
            'note': kw.get('note', obj.get('note', '')),
            'percent': int(kw['percent']) if kw.get('percent', '').isdigit() else obj.get('percent'),
            'started_at': obj.get('started_at') if obj.get('kind') == kind and obj.get('started_at') else now(),
        })
        if kw.get('eta') and kw['eta'].isdigit():
            obj['eta_min'] = int(kw['eta'])
        print(json.dumps(write(obj), ensure_ascii=False))
    else:
        print(__doc__ or 'usage: activity.py [get|set|clear]'); sys.exit(2)

if __name__ == '__main__':
    main()
