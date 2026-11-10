#!/usr/bin/env python3
"""skill-usage.py —— 技能使用与优化闭环（2026-11-10 主公令）

记录每次使用技能的结果；报告出「该优化的、该合并的、该退休的」。
用法：
  python3 tools/skill-usage.py use <skill> ok|fail [说明...] [task=N]
  python3 tools/skill-usage.py report [--days 30]
  python3 tools/skill-usage.py stats <skill>
数据：state/skills/usage.jsonl（只追加）
"""
import json, os, sys, time, glob

W = '/home/j/.openclaw/workspace'
SHARED = '/home/j/.openclaw/shared-skills'
LOG = os.environ.get('SKILL_USAGE_LOG') or os.path.join(W, 'state/skills/usage.jsonl')
os.makedirs(os.path.dirname(LOG), exist_ok=True)


def emit(o):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(o, ensure_ascii=False) + chr(10))


def cmd_use(args):
    if len(args) < 2:
        print('用法: use <skill> ok|fail [说明] [task=N]'); return 2
    skill, outcome = args[0], args[1]
    note, task = '', None
    for a in args[2:]:
        if a.startswith('task='):
            task = a.split('=', 1)[1]
        else:
            note = (note + ' ' + a).strip()
    if outcome not in ('ok', 'fail', 'partial'):
        print('outcome 只能是 ok/fail/partial'); return 2
    emit({'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'skill': skill,
          'outcome': outcome, 'note': note, 'task': task})
    print('记录 %s %s' % (skill, outcome))
    return 0


def load():
    rows = []
    if not os.path.exists(LOG):
        return rows
    for line in open(LOG, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def skills():
    return sorted(os.path.basename(p) for p in glob.glob(SHARED + '/*')
                  if os.path.isdir(p) and not os.path.basename(p).startswith('.'))


def age_days(ts):
    try:
        t = time.mktime(time.strptime(ts, '%Y-%m-%dT%H:%M:%S'))
    except Exception:
        return 999
    return (time.time() - t) / 86400.0


def cmd_report(args):
    days = 30
    if '--days' in args:
        days = int(args[args.index('--days') + 1])
    rows = [r for r in load() if age_days(r['ts']) <= days]
    per = {}
    for r in rows:
        d = per.setdefault(r['skill'], {'ok': 0, 'fail': 0, 'partial': 0, 'last': '', 'notes': []})
        d[r['outcome']] = d.get(r['outcome'], 0) + 1
        if r['ts'] > d['last']:
            d['last'] = r['ts']
        if r['note']:
            d['notes'].append(r['note'])
    print('近 %d 天：%d 次使用 / %d 个技能 / 共享技能库 %d 个' % (days, len(rows), len(per), len(skills())))
    fseen = {}
    try:
        with open(os.path.join(W, 'state/skills/registry.jsonl'), encoding='utf-8') as _f:
            for _l in _f:
                _l = _l.strip()
                if not _l:
                    continue
                try:
                    _o = json.loads(_l)
                except Exception:
                    continue
                if _o.get('skill') and _o['skill'] not in fseen:
                    fseen[_o['skill']] = _o.get('first_seen') or ''
    except Exception:
        pass
    today_s = time.strftime('%Y-%m-%d')
    todo, unused, okn = [], [], 0
    for name in skills():
        d = per.get(name)
        if not d:
            # 未使用天数按「首次见到」算，新建技能不会一出生就被判老
            anchor = fseen.get(name) or today_s
            if age_days(anchor + 'T00:00:00') >= days:
                unused.append(name)
            else:
                okn += 1
            continue
        fails = d.get('fail', 0)
        uses = sum(v for k, v in d.items() if k in ('ok', 'fail', 'partial'))
        last_age = age_days(d['last'])
        if fails >= 2 and fails / float(uses) >= 0.34:
            todo.append((name, '失败 %d/%d，需补坑或改步骤' % (fails, uses)))
        elif fails >= 1:
            todo.append((name, '失败 %d 次，观察' % fails))
        elif last_age > 45:
            unused.append(name)
        else:
            okn += 1
    if todo:
        print(chr(10) + '🔴 待优化：')
        for n, why in todo:
            print('  - %s —— %s' % (n, why))
    print(chr(10) + '🟢 正常：%d 个' % okn)
    if unused:
        print('⚪ %d 天以上未使用（按首见日计，候选合并/退休）：%s' % (days, ', '.join(unused[:12]) + (' …' if len(unused) > 12 else '')))
    return 0


def cmd_stats(args):
    if not args:
        print('用法: stats <skill>'); return 2
    rows = [r for r in load() if r['skill'] == args[0]]
    print('%s：共 %d 次' % (args[0], len(rows)))
    for r in rows[-10:]:
        print('  %s %s %s' % (r['ts'], r['outcome'], r['note']))
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    cmd = sys.argv[1]
    if cmd == 'use':
        return cmd_use(sys.argv[2:])
    if cmd == 'report':
        return cmd_report(sys.argv[2:])
    if cmd == 'stats':
        return cmd_stats(sys.argv[2:])
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main())
