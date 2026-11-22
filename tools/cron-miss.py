#!/usr/bin/env python3
"""cron-miss.py —— 找「该跑没跑」的定时任务（零 token）

判据：按 cron 表达式回推最近一次应触发时刻；若该时刻已过 10 分钟，
而 state.lastRunAtMs 仍早于它 5 分钟以上，判为漏跑。

重激活豁免（2026-11-22 加）：state.scheduleActivatedAtMs 晚于本次应触发时刻的，
该档位一律不算漏跑（排程被停用后再启用，档位本就不该跑）。

改档豁免（2026-11-21 加）：排程表达式换过后，新档位的「下一次应触发」之前
一律不算漏跑（旧档位本就不该在新时刻跑）。指纹存 state/work/cron-sched.json，
字段 {id: {"expr": "...", "grace_until": "YYYY-MM-DD HH:MM"}}。

用法：python3 tools/cron-miss.py [--hours 26] [--json] [--no-grace]
"""
import argparse, json, os, re, subprocess, sys

W = '/home/j/.openclaw/workspace'
SCHED_FILE = os.path.join(W, 'state/work/cron-sched.json')
from datetime import datetime, timedelta


def field_match(field, val, lo, hi):
    for part in field.split(','):
        part = part.strip()
        if not part:
            continue
        if part == '*':
            return True
        if '/' in part:
            rng, step = part.split('/', 1)
            step = int(step)
            if rng == '*':
                if (val - lo) % step == 0:
                    return True
            else:
                a, _, b = rng.partition('-')
                a = int(a)
                b = int(b) if b else hi
                if a <= val <= b and (val - a) % step == 0:
                    return True
        elif '-' in part:
            a, b = part.split('-', 1)
            if int(a) <= val <= int(b):
                return True
        else:
            if int(part) == val:
                return True
    return False


def matches(expr, dt):
    p = expr.split()
    if len(p) != 5:
        return False
    mi, hh, dom, mon, dow = p
    if not field_match(mi, dt.minute, 0, 59):
        return False
    if not field_match(hh, dt.hour, 0, 23):
        return False
    if not field_match(mon, dt.month, 1, 12):
        return False
    if dom != '*' and not field_match(dom, dt.day, 1, 31):
        return False
    if dow != '*' and not field_match(dow, (dt.weekday() + 1) % 7, 0, 6):
        return False
    return True


def last_fire(expr, now, hours):
    t = now.replace(second=0, microsecond=0)
    for _ in range(int(hours * 60) + 1):
        if matches(expr, t):
            return t
        t -= timedelta(minutes=1)
    return None


def next_fire(expr, now, days=8):
    t = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(days * 24 * 60):
        if matches(expr, t):
            return t
        t += timedelta(minutes=1)
    return None


def load_sched():
    try:
        raw = json.load(open(SCHED_FILE))
    except Exception:
        raw = {}
    out = {}
    for k, v in raw.items():
        if isinstance(v, str):          # 旧格式：id -> expr
            out[k] = {'expr': v, 'grace_until': None}
        elif isinstance(v, dict):
            out[k] = {'expr': v.get('expr'), 'grace_until': v.get('grace_until')}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hours', type=int, default=26)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--no-grace', action='store_true')
    a = ap.parse_args()
    out = subprocess.run(['openclaw', 'cron', 'list', '--json'], capture_output=True, text=True, timeout=180)
    try:
        d = json.loads(out.stdout)
    except Exception:
        print('cron list 取不到')
        return 2
    jobs = d if isinstance(d, list) else d.get('jobs', [])
    now = datetime.now()
    SCHED = {} if a.no_grace else load_sched()
    SCHED0 = json.loads(json.dumps(SCHED))
    misses = []
    rescheduled = []
    reactivated = []
    for j in jobs:
        if not j.get('enabled', True):
            continue
        sch = j.get('schedule') or {}
        if sch.get('kind') not in (None, 'cron'):
            continue
        expr = sch.get('expr') or sch.get('cron')
        if not expr or expr.startswith('@') or not re.fullmatch(r'\d+ \d+ .*', expr):
            continue
        lf = last_fire(expr, now, a.hours)
        if not lf:
            continue
        if (now - lf) < timedelta(minutes=10):
            continue
        act_ms = (j.get('state') or {}).get('scheduleActivatedAtMs')
        if act_ms:
            act = datetime.fromtimestamp(act_ms / 1000)
            if lf < act and (now - act) < timedelta(hours=48):
                reactivated.append({'name': j.get('name'), 'expected': lf.strftime('%m-%d %H:%M'),
                                    'activated': act.strftime('%Y-%m-%d %H:%M')})
                continue
        jid = j.get('id')
        rec = SCHED.get(jid)
        grace = None
        if not a.no_grace:
            if rec is None or rec.get('expr') != expr:
                nf = next_fire(expr, now)
                grace = nf.strftime('%Y-%m-%d %H:%M') if nf else None
                SCHED[jid] = {'expr': expr, 'grace_until': grace}
                rescheduled.append({'name': j.get('name'), 'old': (rec or {}).get('expr') or '-',
                                    'new': expr, 'expected': lf.strftime('%m-%d %H:%M')})
                if grace:
                    continue
            else:
                grace = rec.get('grace_until')
                if grace and lf < datetime.strptime(grace, '%Y-%m-%d %H:%M'):
                    continue
        st = j.get('state') or {}
        ms = st.get('lastRunAtMs')
        last = datetime.fromtimestamp(ms / 1000) if ms else None
        if last and last >= lf - timedelta(minutes=5):
            continue
        misses.append({'agent': j.get('agentId'), 'name': j.get('name'), 'expr': expr,
                       'expected': lf.strftime('%m-%d %H:%M'),
                       'last': last.strftime('%m-%d %H:%M') if last else 'never'})
    if not a.no_grace and SCHED != SCHED0:
        try:
            os.makedirs(os.path.dirname(SCHED_FILE), exist_ok=True)
            json.dump(SCHED, open(SCHED_FILE, 'w'), ensure_ascii=False, indent=1)
        except Exception:
            pass
    if rescheduled:
        sys.stderr.write('改档豁免 %d 个（新档位未到前不计漏跑）: %s\n' % (
            len(rescheduled), ', '.join('%s %s->%s' % (r['name'], r['old'], r['new']) for r in rescheduled)))
    if reactivated:
        sys.stderr.write('重激活豁免 %d 个（激活前档位不计漏跑）: %s\n' % (len(reactivated), ', '.join('%s %s' % (r['name'], r['expected']) for r in reactivated)))
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'state', 'work', 'cron-miss-exempt.jsonl'), 'a') as fh:
                fh.write(json.dumps({'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'exempt': reactivated}, ensure_ascii=False) + '\n')
        except Exception:
            pass
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
