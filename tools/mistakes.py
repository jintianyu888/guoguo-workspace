#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mistakes.py — 错误账本（自我纠错的闭环，2026-11-12）

为什么要有它：光"开会"抓不住重复犯的错。必须把每一次被抓住的错误写成一条，
带上"我当时说什么 / 实际是什么 / 谁抓住的 / 加了什么规则"，按月复盘找模式。

用法：
  python3 tools/mistakes.py add "我当时声称X" "实际是Y" --caught-by glm --evidence "命令与输出" --rule "新增的检查"
  python3 tools/mistakes.py list [--month 202611]
  python3 tools/mistakes.py stats
"""
import json, os, sys, time

WS = '/home/j/.openclaw/workspace'
F = os.path.join(WS, 'state', 'decisions', 'mistakes.jsonl')

def load():
    if not os.path.exists(F):
        return []
    out = []
    with open(F, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out

def save(items):
    tmp = F + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')
    os.replace(tmp, F)

def cmd_add(args):
    claimed, actual = args[0], args[1]
    caught = 'self'; evidence = ''; rule = ''
    i = 2
    while i < len(args):
        if args[i] == '--caught-by':
            caught = args[i+1]; i += 2
        elif args[i] == '--evidence':
            evidence = args[i+1]; i += 2
        elif args[i] == '--rule':
            rule = args[i+1]; i += 2
        else:
            i += 1
    items = load()
    mid = 'M-%s-%03d' % (time.strftime('%Y%m%d'), len([x for x in items if x['date'] == time.strftime('%Y%m%d')]) + 1)
    items.append({'id': mid, 'date': time.strftime('%Y%m%d'), 'at': time.strftime('%Y-%m-%dT%H:%M:%S'),
                  'claimed': claimed, 'actual': actual, 'caught_by': caught,
                  'evidence': evidence, 'rule_added': rule})
    save(items)
    print(mid)
    return 0

def cmd_list(args):
    month = ''
    for i, a in enumerate(args):
        if a == '--month':
            month = args[i+1]
    items = [x for x in load() if not month or x['date'].startswith(month)]
    if not items:
        print('（无记录）'); return 0
    for x in items:
        print('%s %s [%s]' % (x['id'], x['date'], x['caught_by']))
        print('  声称：%s' % x['claimed'])
        print('  实际：%s' % x['actual'])
        if x['rule_added']:
            print('  规则：%s' % x['rule_added'])
    return 0

def cmd_stats(args):
    items = load()
    if not items:
        print('（无记录）'); return 0
    from collections import Counter
    c = Counter(x['caught_by'] for x in items)
    print('总错误数：%d' % len(items))
    for k, v in c.most_common():
        print('  由 %-10s 抓住 %d 次' % (k, v))
    norule = [x for x in items if not x['rule_added']]
    print('未转成规则的：%d 条' % len(norule))
    return 0


def cmd_review(args):
    items = load()
    if not items:
        print('（无记录）'); return 0
    from collections import Counter
    print('== 错误复盘 ==')
    print('总数：%d' % len(items))
    by_catcher = Counter(x['caught_by'] for x in items)
    print('抓错来源：' + '，'.join('%s %d 次' % (k, v) for k, v in by_catcher.most_common()))
    norule = [x for x in items if not x['rule_added'].strip()]
    print('还没变成规则的：%d 条' % len(norule))
    for x in norule:
        print('  - %s %s' % (x['id'], x['claimed'][:60]))
    rules = [x['rule_added'] for x in items if x['rule_added'].strip()]
    dup = Counter(rules)
    print('重复出现的规则（说明同类错在复发）：')
    any_dup = False
    for r, c in dup.items():
        if c > 1:
            any_dup = True
            print('  %d 次：%s' % (c, r))
    if not any_dup:
        print('  无')
    return 0

def main():
    if len(sys.argv) < 2:
        print(__doc__); return 1
    cmd, a = sys.argv[1], sys.argv[2:]
    return {'add': cmd_add, 'list': cmd_list, 'stats': cmd_stats, 'review': cmd_review}.get(cmd, lambda x: print('未知命令') or 1)(a)

if __name__ == '__main__':
    sys.exit(main())
