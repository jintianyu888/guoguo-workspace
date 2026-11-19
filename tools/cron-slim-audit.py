#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cron-slim-audit.py v1.0 (2026-11-19 主公令)
定期审核全部 cron 任务，找出：重复 / 过期无用 / 频率过高 / 从未跑过 / 长期报错，
输出精简建议清单。零 token，只读。
用法: python3 tools/cron-slim-audit.py [--write]
"""
import json
import subprocess
import sys
import datetime
import collections

CLI = '/home/j/.npm-global/bin/openclaw'
OUT = '/home/j/.openclaw/workspace/state/work/cron-slim-%s.md'


def load():
    d = json.loads(subprocess.run([CLI, 'cron', 'list', '--json'],
                                  capture_output=True, text=True, timeout=120).stdout)
    return d if isinstance(d, list) else d.get('jobs', d)


def minutes(expr):
    f = expr.split()
    if not f:
        return 99999
    m = f[0]
    if m.startswith('*/'):
        try:
            return int(m[2:])
        except ValueError:
            return 99999
    if len(f) > 1 and f[1] == '*':
        return 60
    if len(f) > 1 and ',' in f[1]:
        return 1440 // max(1, len(f[1].split(',')))
    return 1440


def main():
    jobs = load()
    now = datetime.datetime.now()
    L = []
    a = L.append
    a('# cron 任务精简审核 %s' % now.strftime('%Y-%m-%d %H:%M'))
    a('')
    a('总数 %d，启用 %d' % (len(jobs), sum(1 for j in jobs if j.get('enabled'))))
    a('')

    # 1 高频
    a('## 一、高频任务（≤30 分钟一次）')
    for j in sorted(jobs, key=lambda x: minutes((x.get('schedule') or {}).get('expr', ''))):
        e = (j.get('schedule') or {}).get('expr', '')
        mm = minutes(e)
        if mm <= 30:
            a('- %-12s %-26s %s' % (e, j.get('name'), (j.get('payload') or {}).get('kind')))
    a('')

    # 2 报错
    a('## 二、连续报错')
    bad = 0
    for j in jobs:
        st = j.get('state') or {}
        n = st.get('consecutiveErrors') or 0
        if n > 0:
            bad += 1
            a('- err%d %-26s %s' % (n, j.get('name'), (j.get('schedule') or {}).get('expr')))
    if not bad:
        a('- 无')
    a('')

    # 3 从未跑过
    a('## 三、从未跑过（可能配错或已废）')
    never = 0
    for j in jobs:
        st = j.get('state') or {}
        if not st.get('lastRunAtMs') and j.get('enabled'):
            never += 1
            a('- %-26s %s' % (j.get('name'), (j.get('schedule') or {}).get('expr')))
    if not never:
        a('- 无')
    a('')

    # 4 同族重复
    kw = ['快照', '巡检', '哨兵', '告警', '体检', '汇总', '简报', '日报', '检查',
          '核查', '审计', '扫描', '统计', '计数', '备份', '自审', '计划']
    groups = collections.defaultdict(list)
    for j in jobs:
        n = j.get('name') or ''
        for k in kw:
            if k in n:
                groups[k].append((n, (j.get('schedule') or {}).get('expr')))
                break
    a('## 四、同族任务（重点看是否重复建设）')
    for k, v in sorted(groups.items(), key=lambda x: -len(x[1])):
        if len(v) >= 3:
            a('- **[%s] %d 个**' % (k, len(v)))
            for n, e in v:
                a('  - %-26s %s' % (n, e))
    a('')

    # 5 长期未更新（启用但 7 天没跑成功）
    a('## 五、7 天没有成功运行')
    stale = 0
    for j in jobs:
        st = j.get('state') or {}
        lr = st.get('lastRunAtMs')
        if not lr or not j.get('enabled'):
            continue
        age = (now.timestamp() * 1000 - lr) / 86400000.0
        if age > 7:
            stale += 1
            a('- %.0f 天前 %-26s %s' % (age, j.get('name'), (j.get('schedule') or {}).get('expr')))
    if not stale:
        a('- 无')
    a('')

    txt = '\n'.join(L) + '\n'
    print(txt)
    if '--write' in sys.argv:
        p = OUT % now.strftime('%Y%m%d')
        open(p, 'w').write(txt)
        print('已写入', p)

    # 摘要 + 违规检查
    high = [o for o in ((j.get('name'), (j.get('schedule') or {}).get('expr','')) for j in jobs)
            if minutes(o[1]) <= 30]
    summary = 'cron 精简审核：总 %d 个；30 分钟内高频 %d 个；报错 %d；从未跑过 %d；7 天未成功 %d' % (
        len(jobs), len(high), bad, never, stale)
    print(summary)
    if '--check' in sys.argv and len(high) > 3:
        return 1
    if '--notify' in sys.argv:
        subprocess.run(['bash', '/home/j/.openclaw/workspace/tools/notify.sh', '--digest', summary], timeout=120)
    return 0


if __name__ == '__main__':
    sys.exit(main())
