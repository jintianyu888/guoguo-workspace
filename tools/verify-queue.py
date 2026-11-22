#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify-queue.py —— 交付验收队列（机器验收，零 token）

主公 2026-11-22 令：所有工作都要有查验完成的机制。
用法：
  python3 tools/verify-queue.py add "<任务名>" "<验收命令>"
  python3 tools/verify-queue.py check    # 复跑全部，rc=1 表示有失败
  python3 tools/verify-queue.py list
  python3 tools/verify-queue.py done "<任务名>"
存储：state/verify/queue.json  报告：state/verify/report-latest.md
"""
import json, os, subprocess, sys, time

W = '/home/j/.openclaw/workspace'
Q = os.path.join(W, 'state/verify/queue.json')
RPT = os.path.join(W, 'state/verify/report-latest.md')
os.makedirs(os.path.dirname(Q), exist_ok=True)


def load():
    if not os.path.exists(Q):
        return {'items': []}
    try:
        return json.load(open(Q, encoding='utf-8'))
    except Exception:
        return {'items': []}


def save(d):
    json.dump(d, open(Q, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def cmd_add(name, cmd):
    d = load()
    for it in d['items']:
        if it['name'] == name:
            it['cmd'] = cmd
            break
    else:
        d['items'].append({'name': name, 'cmd': cmd, 'added': time.strftime('%Y-%m-%d %H:%M'),
                           'last_ok': None, 'last_rc': None, 'fails': 0, 'checks': 0})
    save(d)
    print('已登记:', name)


def cmd_done(name):
    d = load()
    before = len(d['items'])
    d['items'] = [it for it in d['items'] if it['name'] != name]
    save(d)
    print('移出:', name, '剩余', len(d['items']), '/', before)


def cmd_check():
    d = load()
    if not d['items']:
        print('队列为空')
        return 0
    out_lines = ['# 验收复跑 ' + time.strftime('%Y-%m-%d %H:%M'), '']
    bad = 0
    for it in d['items']:
        it['checks'] = it.get('checks', 0) + 1
        try:
            p = subprocess.run(['bash', '-lc', it['cmd']], capture_output=True, text=True, timeout=180)
            rc = p.returncode
            out = (p.stdout or '') + (p.stderr or '')
        except subprocess.TimeoutExpired:
            rc, out = 124, 'TIMEOUT(180s)'
        it['last_rc'] = rc
        now = time.strftime('%Y-%m-%d %H:%M')
        if rc == 0:
            it['last_ok'] = now
            it['fails'] = 0
            mark = '[OK]'
        else:
            it['fails'] = it.get('fails', 0) + 1
            mark = '[BAD]' if it['fails'] >= 3 else '[WARN]'
            bad += 1
        out_lines.append('- %s %s  rc=%s  连续失败=%s  上次通过=%s' % (
            mark, it['name'], rc, it['fails'], it['last_ok'] or '未通过'))
        if rc != 0:
            out_lines.append('    ' + (out.strip().replace(chr(10), ' | ')[:600] or '(无输出)'))
    save(d)
    open(RPT, 'w', encoding='utf-8').write(chr(10).join(out_lines) + chr(10))
    print(chr(10).join(out_lines))
    return 1 if bad else 0


def cmd_list():
    d = load()
    for it in d['items']:
        print('%-28s rc=%s 失败=%s 上次=%s' % (it['name'], it['last_rc'], it['fails'], it['last_ok']))
        print('    ' + it['cmd'])
    print('共', len(d['items']), '条')


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(0)
    if a[0] == 'add' and len(a) >= 3:
        cmd_add(a[1], a[2])
    elif a[0] == 'done' and len(a) >= 2:
        cmd_done(a[1])
    elif a[0] == 'check':
        sys.exit(cmd_check())
    elif a[0] == 'list':
        cmd_list()
    else:
        print(__doc__); sys.exit(2)
