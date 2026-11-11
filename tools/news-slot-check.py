#!/usr/bin/env python3
"""news-slot-check.py —— 查新闻简报当天三个档位是否都跑过（零 token）

用法：python3 tools/news-slot-check.py [YYYY-MM-DD]
rc=0 该到的档位都到位；rc=1 有档位缺失（打印缺哪几档）

2026-11-11 改：只核对「已到点」的档位（到点后 GRACE_MIN 分钟才算该到），
未到点的档位不算缺。判据放宽为两条任一成立即算到位：
  1) cron_run_receipts 里该档 status=ok（网关内 cron 正常触发）
  2) state/work/news-brief.log 里该档有「推送 rc=0」（网关外补位 timer 补发）
旧版把未到点的 19:20 也算缺，导致白天永远 rc=1（假阴性）。
"""
import sqlite3, sys, time, datetime, os

DB = 'file:/home/j/.openclaw/state/openclaw.sqlite?mode=ro'
LOG = '/home/j/.openclaw/workspace/state/work/news-brief.log'
JOB = 'e3bcbd06'
SLOTS = ['08:20', '12:20', '19:20']
GRACE_MIN = 20


def log_slots(day):
    """从推送日志里取该日期各档的推送结果：{'08:20': 0, ...}"""
    out = {}
    if not os.path.exists(LOG):
        return out
    prefix = '== %s ' % day
    cur = None
    with open(LOG, errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            if line.startswith(prefix):
                cur = line[len(prefix):len(prefix) + 5]
                continue
            if line.startswith('== '):
                cur = None
                continue
            if cur and line.startswith('推送 rc='):
                try:
                    out[cur] = int(line.split('=', 1)[1])
                except ValueError:
                    out[cur] = -1
                cur = None
    return out


def main():
    now = datetime.datetime.now()
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    day = arg or now.strftime('%Y-%m-%d')
    is_today = (day == now.strftime('%Y-%m-%d'))
    base = time.mktime(time.strptime(day, '%Y-%m-%d'))
    lo, hi = int(base * 1000), int((base + 86400) * 1000)

    c = sqlite3.connect(DB, uri=True)
    rows = c.execute('select started_at_ms,status from cron_run_receipts '
                     'where job_id like ? and started_at_ms between ? and ?',
                     (JOB + '%', lo, hi)).fetchall()
    got = {}
    for ms, st in rows:
        k = time.strftime('%H:%M', time.localtime(ms / 1000))
        if st == 'ok':
            got[k] = 'ok'
    pushed = log_slots(day)

    def hhmm(s):
        h, m = s.split(':')
        return int(h) * 60 + int(m)

    now_min = now.hour * 60 + now.minute
    due = [s for s in SLOTS if (not is_today) or now_min >= hhmm(s) + GRACE_MIN]

    miss = [s for s in due
            if not (any(k[:5] == s and v == 'ok' for k, v in got.items())
                    or pushed.get(s) == 0)]

    detail = []
    for s in due:
        if s in miss:
            continue
        src = 'cron' if any(k[:5] == s and v == 'ok' for k, v in got.items()) else '补位'
        detail.append('%s %s' % (s, src))

    if miss:
        print('%s 缺档：%s（到位：%s）' % (day, ','.join(miss), ', '.join(detail) or '无'))
        return 1
    print('%s 该到的 %d 档齐全（%s）' % (day, len(due), ', '.join(detail) or '尚未到点'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
