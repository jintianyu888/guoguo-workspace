#!/usr/bin/env python3
"""cron-miss.py —— 找「该跑没跑」的定时任务（零 token）

判据：按 cron 表达式回推最近一次应触发时刻；若该时刻已过 10 分钟，
而 state.lastRunAtMs 仍早于它 5 分钟以上，判为漏跑。
用法：python3 tools/cron-miss.py [--hours 26] [--json]
"""
import argparse, json, subprocess, sys
from datetime import datetime, timedelta

def field_match(field, val, lo, hi):
    for part in field.split(','):
        part = part.strip()
        step = 1
        if '/' in part:
            part, s = part.split('/', 1)
            try: step = int(s)
            except ValueError: return False
        if part == '*':
            rng = range(lo, hi + 1)
        elif '-' in part:
            a, b = part.split('-', 1)
            try: rng = range(int(a), int(b) + 1)
            except ValueError: return False
        else:
            try: v = int(part)
            except ValueError: return False
            rng = [v]
        if val in rng and (val - rng[0]) % step == 0:
            return True
    return False

def matches(expr, dt):
    p = expr.split()
    if len(p) != 5: return False
    mi, hh, dom, mon, dow = p
    if not field_match(mi, dt.minute, 0, 59): return False
    if not field_match(hh, dt.hour, 0, 23): return False
    if not field_match(mon, dt.month, 1, 12): return False
    if dom != '*' and not field_match(dom, dt.day, 1, 31): return False
    if dow != '*' and not field_match(dow, (dt.weekday() + 1) % 7, 0, 6): return False
    return True

def last_fire(expr, now, hours):
    t = now.replace(second=0, microsecond=0)
    for _ in range(int(hours * 60) + 1):
        if matches(expr, t):
            return t
        t -= timedelta(minutes=1)
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hours', type=int, default=26)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    out = subprocess.run(['openclaw', 'cron', 'list', '--json'], capture_output=True, text=True, timeout=180)
    try:
        d = json.loads(out.stdout)
    except Exception:
        print('cron list 取不到'); return 2
    jobs = d if isinstance(d, list) else d.get('jobs', [])
    now = datetime.now()
    misses = []
    for j in jobs:
        if not j.get('enabled', True): continue
        sch = j.get('schedule') or {}
        if sch.get('kind') not in (None, 'cron'): continue
        expr = sch.get('expr') or sch.get('cron')
        if not expr or expr.startswith('@'): continue
        lf = last_fire(expr, now, a.hours)
        if not lf: continue
        if (now - lf) < timedelta(minutes=10): continue
        st = j.get('state') or {}
        ms = st.get('lastRunAtMs')
        last = datetime.fromtimestamp(ms / 1000) if ms else None
        if last and last >= lf - timedelta(minutes=5):
            continue
        misses.append({'agent': j.get('agentId'), 'name': j.get('name'), 'expr': expr,
                       'expected': lf.strftime('%m-%d %H:%M'),
                       'last': last.strftime('%m-%d %H:%M') if last else 'never'})
    misses.sort(key=lambda x: x['expected'])
    if a.json:
        print(json.dumps(misses, ensure_ascii=False, indent=1))
    else:
        print('漏跑 %d 个（回看 %dh）' % (len(misses), a.hours))
        for m in misses:
            print('  %s [%s] %s（应跑 %s，实跑 %s）' % (m['agent'], m['expr'], m['name'], m['expected'], m['last']))
    return 0 if not misses else 1

if __name__ == '__main__':
    sys.exit(main())
