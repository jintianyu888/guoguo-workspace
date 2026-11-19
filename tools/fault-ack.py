#!/usr/bin/env python3
# fault-ack.py v1.1 (2026-11-19) —— 已认领故障清单：知道原因、在等修复窗口的，先别刷屏
# 用法:
#   python3 tools/fault-ack.py add <任务名或ID> [--hours 72] [--note 说明]
#   python3 tools/fault-ack.py list
#   python3 tools/fault-ack.py rm <任务名或ID>
#   python3 tools/fault-ack.py check <任务名或ID>   # 退出码 0=已认领 1=未认领
import json, os, sys, time

W = '/home/j/.openclaw/workspace'
P = W + '/state/work/fault-ack.json'


def load():
    if os.path.exists(P):
        try:
            return json.load(open(P)) or {}
        except Exception:
            return {}
    return {}


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ('add', 'list', 'rm', 'check'):
        print('usage: add|list|rm|check'); return 2
    d = load()

    if a[0] == 'check':
        if len(a) < 2:
            return 2
        v = d.get(a[1]) or {}
        return 0 if (v and v.get('until', 0) > time.time()) else 1

    if a[0] == 'list':
        now = time.time()
        for k, v in d.items():
            left = int((v.get('until', 0) - now) / 3600)
            print('%-40s 剩 %3dh  %s' % (k, left, v.get('note', '')))
        return 0

    if len(a) < 2:
        print('缺少任务名'); return 2
    key = a[1]

    if a[0] == 'rm':
        d.pop(key, None)
        json.dump(d, open(P, 'w'), ensure_ascii=False, indent=1)
        print('已移除', key); return 0

    hours, note = 72, ''
    if '--hours' in a:
        hours = int(a[a.index('--hours') + 1])
    if '--note' in a:
        note = a[a.index('--note') + 1]
    d[key] = {'until': time.time() + hours * 3600, 'note': note}
    os.makedirs(os.path.dirname(P), exist_ok=True)
    json.dump(d, open(P, 'w'), ensure_ascii=False, indent=1)
    print('已认领 %s，%dh 内不即时推' % (key, hours))
    return 0


if __name__ == '__main__':
    sys.exit(main())
