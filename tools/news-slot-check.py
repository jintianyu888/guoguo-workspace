#!/usr/bin/env python3
"""news-slot-check.py —— 查新闻简报当天三个档位是否都跑过（零 token）

用法：python3 tools/news-slot-check.py [YYYY-MM-DD]
rc=0 全部到位；rc=1 有档位缺失（打印缺哪几档）
"""
import sqlite3, sys, time

DB = 'file:/home/j/.openclaw/state/openclaw.sqlite?mode=ro'
JOB = 'e3bcbd06'
SLOTS = ['08:20', '12:20', '19:20']


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else time.strftime('%Y-%m-%d')
    base = time.mktime(time.strptime(day, '%Y-%m-%d'))
    lo, hi = int(base * 1000), int((base + 86400) * 1000)
    c = sqlite3.connect(DB, uri=True)
    rows = c.execute('select started_at_ms,status from cron_run_receipts '
                     'where job_id like ? and started_at_ms between ? and ?',
                     (JOB + '%', lo, hi)).fetchall()
    got = {}
    for ms, st in rows:
        got.setdefault(time.strftime('%H:%M', time.localtime(ms / 1000)), st)
    miss = [s for s in SLOTS if not any(k[:5] == s and v == 'ok' for k, v in got.items())]
    if miss:
        print('%s 缺档：%s（实跑：%s）' % (day, ','.join(miss),
              ', '.join('%s %s' % (k, v) for k, v in sorted(got.items())) or '无'))
        return 1
    print('%s 三档齐全' % day)
    return 0


if __name__ == '__main__':
    sys.exit(main())
