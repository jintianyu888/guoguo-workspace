#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""claim-check.py — 断言体检（零 token，2026-11-12）

作用：在把"已完成/已生效/已修复/无风险/不易"这类绝对断言写进议案、汇报、worklog 之前，
机械地挑出**没有证据支撑的绝对断言**，逼我补 evidence 或改成"待验假设"。

用法：
  python3 tools/claim-check.py "文本或文件路径"
退出码：0 无问题 / 1 发现问题

设计取舍：不做语义判断，只做模式匹配 + 就近找证据。宁可误报，不可漏报。
"""
import re, sys, os

TRIGGERS = [
    r'已(经)?(生效|修复|完成|解决|改好|改完|部署|上线)',
    r'不会再?出现', r'没问题', r'无风险', r'稳定了', r'没有影响',
    r'(不易|无法|不可能|做不到|没法)',
    r'全部(通过|正常|完成)', r'一切正常',
]
EVIDENCE = re.compile(r'(evidence|证据|实测|输出|命令|rc=|exit=|→|->|pid=|sha256|HTTP \\d{3}|\\d{3} OK)', re.I)

def load(target):
    if os.path.exists(target):
        return open(target, encoding='utf-8', errors='ignore').read()
    return target

def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    text = load(sys.argv[1])
    lines = text.splitlines()
    hits = []
    for i, line in enumerate(lines):
        for pat in TRIGGERS:
            if re.search(pat, line):
                window = ' '.join(lines[max(0, i-1):i+2])
                if not EVIDENCE.search(window):
                    hits.append((i+1, line.strip()[:120]))
                break
    if not hits:
        print('CLAIM_OK 无裸断言')
        return 0
    print('发现 %d 处无证据的绝对断言：' % len(hits))
    for ln, line in hits:
        print('  L%-4d %s' % (ln, line))
    print('')
    print('处理：补 evidence（命令+输出），或改成待验假设（未验证）。')
    return 1

if __name__ == '__main__':
    sys.exit(main())
