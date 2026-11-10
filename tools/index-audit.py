#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""index.csv 只读审计：作曲家/难度分布、可疑重复、坏文件名。
用法: python3 tools/index-audit.py [--csv PATH] [--json]
退出码固定 0（只做审计，不做修改）；读不到文件才 1。
"""
import argparse, collections, csv, json, os, re, sys

DEFAULT = '/home/j/openclaw-workspaces/print/scores/index.csv'
EXT = ('.pdf', '.jpg', '.png', '.jpeg')

def load(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def norm(t):
    return re.sub(r'[\s\-_,，、·\.]+', '', (t or '').lower())

def audit(rows):
    total = len(rows)
    comp = collections.Counter((r.get('作曲家') or '').strip() or '(空)' for r in rows)
    diff = collections.Counter((r.get('难度') or '').strip() or '(空)' for r in rows)
    bad = [r for r in rows if not (r.get('文件名') or '').strip().lower().endswith(EXT)]
    fn = collections.Counter((r.get('文件名') or '').strip() for r in rows)
    fn_dup = {k: v for k, v in fn.items() if v > 1}
    groups = collections.defaultdict(list)
    for r in rows:
        groups[(norm(r.get('曲名')), (r.get('作曲家') or '').strip())].append(r)
    dup = {k: v for k, v in groups.items() if len(v) > 1}
    # 真实重复：同名同作曲家且文件名完整、互不相同
    real = {k: v for k, v in dup.items()
            if len({x.get('文件名') for x in v}) > 1
            and all((x.get('文件名') or '').lower().endswith(EXT) for x in v)}
    return {
        'total': total,
        'composers_distinct': len(comp),
        'composer_top': comp.most_common(10),
        'difficulty': diff.most_common(),
        'difficulty_unknown_pct': round(100.0 * diff.get('待确认', 0) / total, 1) if total else 0,
        'filename_bad': len(bad),
        'filename_bad_pct': round(100.0 * len(bad) / total, 1) if total else 0,
        'filename_dup_groups': len(fn_dup),
        'title_dup_groups': len(dup),
        'title_dup_real_groups': len(real),
        'title_dup_examples': [{'title': k[0][:60], 'composer': k[1], 'rows': len(v)}
                               for k, v in sorted(dup.items(), key=lambda x: -len(x[1]))[:5]],
        'real_dup_examples': [{'title': k[0][:60], 'composer': k[1], 'rows': len(v)}
                              for k, v in sorted(real.items(), key=lambda x: -len(x[1]))[:5]],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=DEFAULT)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    if not os.path.isfile(a.csv):
        print('MISSING ' + a.csv, file=sys.stderr)
        return 1
    rows = load(a.csv)
    res = audit(rows)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    print('文件: %s' % a.csv)
    print('总行数: %d' % res['total'])
    print('作曲家 distinct: %d | top: %s' % (res['composers_distinct'],
          ', '.join('%s %d' % x for x in res['composer_top'][:6])))
    print('难度分布: %s | 待确认占 %.1f%%' % (
          ', '.join('%s %d' % x for x in res['difficulty']), res['difficulty_unknown_pct']))
    print('坏文件名(无扩展名/被点号截断): %d (%.1f%%)' % (res['filename_bad'], res['filename_bad_pct']))
    print('文件名重复组: %d | 同名同作曲家组: %d | 其中真重复(文件名完整且不同): %d'
          % (res['filename_dup_groups'], res['title_dup_groups'], res['title_dup_real_groups']))
    for x in res['title_dup_examples']:
        print('  ~ %s | %s | %d 行' % (x['title'], x['composer'], x['rows']))
    for x in res['real_dup_examples']:
        print('  ! %s | %s | %d 行' % (x['title'], x['composer'], x['rows']))
    return 0

if __name__ == '__main__':
    sys.exit(main())
