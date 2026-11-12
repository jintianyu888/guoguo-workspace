#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cred-check.py — 凭据卫生哨兵（2026-11-12）

检查：私钥/凭据文件权限是否过宽、配置里是否残留明文密钥样式字符串（只报位置不打印值）。
"""
import os, re, stat, sys, subprocess

WS = '/home/j/.openclaw/workspace'
PATHS = ['/home/j/.openclaw/tls/gw.key',
         '/home/j/.ssh/id_ed25519',
         '/home/j/.openclaw/browser-feishu']
KEYRE = re.compile(r'\b(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,})\b')

def perm_check():
    bad = []
    for p in PATHS:
        if not os.path.exists(p):
            continue
        m = os.stat(p).st_mode & 0o777
        if os.path.isdir(p):
            if m & 0o077:
                bad.append('%s 目录权限 %o（应 700）' % (p, m))
        elif m & 0o077:
            bad.append('%s 权限 %o（应 600）' % (p, m))
    return bad

def secret_scan():
    hits = []
    for root, dirs, files in os.walk('/home/j/.openclaw'):
        dirs[:] = [d for d in dirs if d not in ('node_modules', '.git', 'venvs', 'browser-feishu', 'state')]
        for f in files:
            if not f.endswith(('.json', '.yaml', '.yml', '.env', '.toml')):
                continue
            p = os.path.join(root, f)
            try:
                if os.path.getsize(p) > 2_000_000:
                    continue
                s = open(p, encoding='utf-8', errors='ignore').read()
            except Exception:
                continue
            if KEYRE.search(s):
                hits.append(p)
            if len(hits) > 10:
                return hits
    return hits

def main():
    bad = perm_check()
    hits = secret_scan()
    if not bad and not hits:
        print('CRED_OK 权限合规，未见明文密钥样式串')
        return 0
    if bad:
        print('CRED_WARN 权限：' + '；'.join(bad))
    if hits:
        print('CRED_WARN 疑似明文密钥：' + '；'.join(hits[:10]) + '（只报位置，不打印值）')
    return 1

if __name__ == '__main__':
    sys.exit(main())
