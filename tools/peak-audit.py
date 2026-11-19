#!/usr/bin/env python3
# peak-audit.py v1.0 (2026-11-19) —— 审计：哪些管家任务会落在工作日高峰（09-12/14-18）
# 用法: python3 tools/peak-audit.py [--json]
import json, subprocess, sys

CLI = '/home/j/.npm-global/bin/openclaw'
PEAK_HOURS = set([9, 10, 11, 14, 15, 16, 17])
# 工作日 = 1-5（cron dow: 0/7=Sun, 1=Mon ... 6=Sat）


def expand(field, lo, hi):
    out = set()
    for part in field.split(','):
        step = 1
        if '/' in part:
            part, s = part.split('/')
            step = int(s)
        if part == '*':
            rng = range(lo, hi + 1)
        elif '-' in part:
            a, b = part.split('-')
            rng = range(int(a), int(b) + 1)
        else:
            rng = [int(part)]
        for v in rng:
            if (v - lo) % step == 0 or step == 1:
                out.add(v)
    return out


def fires_in_peak(expr):
    f = expr.split()
    if len(f) < 5:
        return False, 'expr 格式不认识'
    _min, hour, _dom, _mon, dow = f[:5]
    hours = expand(hour, 0, 23)
    dows = set()
    for d in dow.split(','):
        if d == '*':
            dows |= set(range(0, 7))
        elif '-' in d:
            a, b = d.split('-')
            dows |= set(range(int(a), int(b) + 1))
        else:
            dows.add(int(d))
    weekday = bool(dows & {1, 2, 3, 4, 5})
    return (weekday and bool(hours & PEAK_HOURS)), ''


def main():
    r = subprocess.run([CLI, 'cron', 'list', '--json'], capture_output=True, text=True, timeout=120)
    d = json.loads(r.stdout)
    jobs = d if isinstance(d, list) else d.get('jobs', d)
    rows = []
    for j in jobs:
        if not j.get('enabled'):
            continue
        p = j.get('payload') or {}
        kind = p.get('kind') or ''
        # 只有会烧 token 的才算：agent 任务/带 model 的任务
        if kind not in ('agent', 'agentTurn', 'prompt') and not p.get('model'):
            continue
        sch = j.get('schedule') or {}
        expr = sch.get('expr') or ''
        if not expr:
            continue
        hit, why = fires_in_peak(expr)
        if hit:
            rows.append((j.get('name'), expr, kind, j.get('agentId')))
    print('工作日高峰(09-12/14-18)内会触发的烧 token 任务：%d 个' % len(rows))
    for n, e, k, a in sorted(rows, key=lambda x: x[1]):
        print('  %-28s %-14s %-8s %s' % (n, e, k, a))
    if '--json' in sys.argv:
        json.dump([{'name': n, 'expr': e, 'kind': k, 'agent': a} for n, e, k, a in rows],
                  open('/home/j/.openclaw/workspace/state/work/peak-audit.json', 'w'),
                  ensure_ascii=False, indent=1)
    return 1 if rows else 0


if __name__ == '__main__':
    sys.exit(main())
