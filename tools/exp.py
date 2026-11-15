#!/usr/bin/env python3
# exp.py - 先查后做：在成功经验索引/账本/技能/文档里找现成做法
# 用法: python3 tools/exp.py 关键词 [--n 8] [--full]
import json, sys, pathlib, re

WS = pathlib.Path('/home/j/.openclaw/workspace')
IDX = WS / 'state' / 'ledger' / 'exp-index.json'

def main():
    argv = sys.argv[1:]
    args, skip = [], False
    for a in argv:
        if skip:
            skip = False
            continue
        if a == '--n':
            skip = True
            continue
        if a.startswith('--'):
            continue
        args.append(a)
    if not args:
        print(__doc__ or 'usage: exp.py 关键词 [--n 8] [--full]')
        return 2
    q = ' '.join(args).lower()
    n = 8
    full = '--full' in sys.argv
    for i, a in enumerate(sys.argv):
        if a == '--n' and i + 1 < len(sys.argv):
            try:
                n = int(sys.argv[i + 1])
            except ValueError:
                pass
    items = []
    if IDX.exists():
        items = json.loads(IDX.read_text(encoding='utf-8')).get('items', [])
    hits = []
    for it in items:
        title = (it.get('title', '') or '').lower()
        detail = (it.get('detail', '') or '').lower()
        score = title.count(q) * 5 + min(detail.count(q), 3)
        if q in title:
            score += 5
        if score:
            hits.append((score, it))
    hits.sort(key=lambda x: (-x[0], x[1].get('date', '') or ''), reverse=True)
    if not hits:
        print('索引里没有匹配：%s' % q)
        print('试试更短的关键词，或直接 grep：')
        print('  grep -n "%s" /home/j/.openclaw/workspace/state/log/worklog.jsonl' % q)
        return 1
    print('命中 %d 条（显示前 %d）\n' % (len(hits), min(n, len(hits))))
    for score, it in hits[:n]:
        head = '- [%s] %s' % (it.get('cat'), it.get('title'))
        if it.get('date'):
            head += '（%s）' % it['date']
        print(head)
        det = (it.get('detail') or '').replace('\n', ' ')
        if det:
            print('    ' + (det if full else det[:260]))
        if it.get('rollback'):
            print('    回滚：' + (it['rollback'] if full else it['rollback'][:120]))
        print('    来源：' + it.get('source', ''))
    print('\n完整索引：docs/成功经验索引-*.md ；原始账本：state/log/worklog.jsonl')
    return 0

if __name__ == '__main__':
    sys.exit(main())
