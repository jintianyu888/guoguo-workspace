#!/usr/bin/env python3
# 2026-10-03 主公令（选 A）：给 WSL 开镜像网络模式，让 WSL 借 Windows 的网络（含 VPN）
# 2026-10-17 加固：与 wsl-net-guard.sh 共用一个 flock + 原子写，避免并发写坏 .wslconfig
import fcntl, os, sys, time
p = '/mnt/c/Users/J/.wslconfig'
LOCK = '/home/j/.openclaw/workspace/state/work/.wslconfig.lock'
os.makedirs(os.path.dirname(LOCK), exist_ok=True)
with open(LOCK, 'w') as lk:
    fcntl.flock(lk, fcntl.LOCK_EX)
    s = open(p, 'rb').read().decode('utf-8', 'replace')
    if 'networkingMode' in s:
        print('already has networkingMode')
    else:
        if not s.endswith('\n'):
            s += '\n'
        s += 'networkingMode=mirrored\n'
        tmp = p + '.tmp-mirror'
        with open(tmp, 'wb') as f:
            f.write(s.encode('utf-8'))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
        print('added networkingMode=mirrored')
    print('--- 现在内容 ---')
    print(open(p, encoding='utf-8', errors='replace').read())
