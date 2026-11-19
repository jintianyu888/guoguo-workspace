#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mem-digest.py v1.1 (2026-11-19)
把"当天"的会话内容从 lcm.db 抽成一个有界摘要文件，供夜间记忆提炼任务读取。
零 token：只读数据库 + 写文件。lcm.db 的 created_at 是 UTC 文本，这里按本地日换算。

用法: python3 tools/mem-digest.py [--date YYYY-MM-DD] [--max-bytes 60000]
输出: state/memory/digest-YYYY-MM-DD.md
"""
import sqlite3
import sys
import os
import datetime
import re

DB = '/home/j/.openclaw/lcm.db'
OUT = '/home/j/.openclaw/workspace/state/memory/digest-%s.md'
CST = datetime.timezone(datetime.timedelta(hours=8))


def arg(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def main():
    day = arg('--date') or datetime.date.today().isoformat()
    maxb = int(arg('--max-bytes', '60000'))
    d0 = datetime.datetime.strptime(day, '%Y-%m-%d').replace(tzinfo=CST)
    d1 = d0 + datetime.timedelta(days=1)
    fmt = '%Y-%m-%d %H:%M:%S'
    s = d0.astimezone(datetime.timezone.utc).strftime(fmt)
    e = d1.astimezone(datetime.timezone.utc).strftime(fmt)

    c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
    rows = list(c.execute(
        "select conversation_id, content from messages where created_at>=? and created_at<? "
        "and role in ('user','assistant') and content is not null and length(content)>40 "
        "order by created_at", (s, e)))
    src = 'messages'

    seen, buf, used = set(), [], 0
    for cid, content in rows:
        t = re.sub(r'\s+', ' ', str(content)).strip()
        key = t[:120]
        if key in seen:
            continue
        seen.add(key)
        line = '- %s' % t[:500]
        if used + len(line) > maxb:
            break
        buf.append(line)
        used += len(line)

    os.makedirs(os.path.dirname(OUT % day), exist_ok=True)
    p = OUT % day
    open(p, 'w').write('# %s 会话摘要（源 %s，%d 条，%d 字节）\n\n%s\n'
                       % (day, src, len(buf), used, '\n'.join(buf)))
    print('写入 %s（%d 条，%d 字节）' % (p, len(buf), used))
    return 0


if __name__ == '__main__':
    sys.exit(main())
