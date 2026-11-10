#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''facts-audit.py — 跨管家「硬事实」候选扫描（只找候选，不改任何文件）

目的：区分两类东西——
  硬事实（可枚举、机器要读、多家会冲突）→ 应归一到 state/facts/facts.db
  叙事记忆（经验/过程/教训）→ 不合并，走 butler-digest 周蒸馏
输出：state/facts/candidates-<date>.md，每条带来源路径，供人确认。
'''

import os, re, sys
from datetime import datetime

ROOT = '/home/j/openclaw-workspaces'
OUT = '/home/j/.openclaw/workspace/state/facts'

DOMAINS = [
    ('健康指标', r'血压|血糖|体重|心率|用药|过敏'),
    ('家庭硬信息', r'生日|身份证|门牌|楼栋|小区|车牌'),
    ('排期与规则', r'课表|上课时间|琴房|预约规则|值班'),
    ('设备与参数', r'631|ipp/print|print-quality|IP 地址|192\.168'),
    ('额度与钱', r'额度|余额|预算|单价|元/|¥'),
    ('权限与账号', r'权限|账号|密码|token|密钥'),
]

SKIP = re.compile(r'AGENTS\.md$|SOUL\.md$|IDENTITY\.md$|USER\.md$|MEMORY\.md$|DREAMS?\.md$')


def files():
    for dirpath, dirnames, names in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in ('node_modules', '.git', 'venvs')]
        for n in names:
            if not n.endswith('.md') or SKIP.search(n):
                continue
            p = os.path.join(dirpath, n)
            if os.path.getsize(p) > 400000:
                continue
            yield p


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = {k: [] for k, _ in DOMAINS}
    nfiles = 0
    for p in files():
        nfiles += 1
        agent = os.path.relpath(p, ROOT).split(os.sep)[0]
        try:
            txt = open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        for i, ln in enumerate(txt.splitlines(), 1):
            s = ln.strip()
            if len(s) < 6 or len(s) > 180 or s.startswith('<!--'):
                continue
            for dom, pat in DOMAINS:
                if re.search(pat, s):
                    rows[dom].append((agent, '%s:%d' % (os.path.relpath(p, ROOT), i), s))
                    break
    day = datetime.now().strftime('%Y%m%d')
    out = os.path.join(OUT, 'candidates-%s.md' % day)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# 硬事实候选 %s（扫描 %d 份 md；只列候选，未确认）\n\n' % (day, nfiles))
        for dom, _ in DOMAINS:
            lst = rows[dom]
            agents = sorted({a for a, _, _ in lst})
            f.write('## %s（%d 条 / %d 个管家）\n' % (dom, len(lst), len(agents)))
            seen = set()
            shown = 0
            for a, src, s in lst:
                key = re.sub(r'\s+', '', s)[:40]
                if key in seen:
                    continue
                seen.add(key)
                f.write('- [%s] %s（%s）\n' % (a, s, src))
                shown += 1
                if shown >= 25:
                    break
            f.write('\n')
    print('扫描 %d 份 md → %s' % (nfiles, out))
    for dom, _ in DOMAINS:
        print('  %-8s %4d 条 / %2d 管家' % (dom, len(rows[dom]), len({a for a, _, _ in rows[dom]})))
    return 0


if __name__ == '__main__':
    sys.exit(main())
