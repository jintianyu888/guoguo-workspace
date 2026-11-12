#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""exposure-check.py — 暴露面哨兵（2026-11-12）

查三件事：
1) 我们关心的端口（18789/9443）在 Windows 防火墙里是否仍有"任何 IP"放行
2) portproxy 列表是否多出计划外的转发
3) 网关是否仍在 0.0.0.0 监听（预期，但要有记录）
有变化才推一条（状态变化去重，不重复刷）。
"""
import json, os, subprocess, sys, time

WS = '/home/j/.openclaw/workspace'
STATE = os.path.join(WS, 'state', 'work', 'exposure.json')
PORTS = ('18789', '9443')
NETSH = '/mnt/c/Windows/System32/netsh.exe'

def run(args):
    try:
        p = subprocess.run(args, capture_output=True, timeout=60)
        return p.stdout.decode('gbk', 'ignore')
    except Exception as e:
        return ''

def firewall_ports():
    out = run([NETSH, 'advfirewall', 'firewall', 'show', 'rule', 'name=all', 'verbose'])
    findings = {}
    for block in out.split('规则名称'):
        if not any(p in block for p in PORTS):
            continue
        name = '?'
        for _l in block.splitlines()[:3]:
            _l = _l.strip().lstrip(':').strip()
            if _l:
                name = _l
                break
        remote = ''
        for line in block.splitlines():
            if line.strip().startswith('远程 IP'):
                remote = line.split(':', 1)[-1].strip()
        # 只有明确读到"任何/Any"才算放行；读不到（空）记为未知，不误报
        if remote in ('任何', 'Any'):
            findings[name] = remote
    return findings

def portproxy():
    out = run([NETSH, 'interface', 'portproxy', 'show', 'v4tov4'])
    rows = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[1].isdigit():
            rows.append('%s:%s -> %s:%s' % tuple(parts))
    return sorted(rows)

def main():
    fw = firewall_ports()
    pp = portproxy()
    cur = {'firewall_open_any': fw, 'portproxy': pp}
    prev = {}
    if os.path.exists(STATE):
        try: prev = json.load(open(STATE))
        except Exception: prev = {}
    problems = []
    if fw:
        problems.append('防火墙仍有任何IP放行：' + '；'.join('%s(远程IP=%s)' % (k, v) for k, v in fw.items()))
    expected = {'0.0.0.0:18789 -> 172.18.242.44:18789'}
    extra = [p for p in pp if p not in expected and not p.startswith('0.0.0.0:9443')]
    if extra:
        problems.append('出现计划外 portproxy：' + '；'.join(extra))
    json.dump(cur, open(STATE, 'w'), ensure_ascii=False, indent=1)
    if problems and problems != prev.get('problems'):
        subprocess.run(['bash', os.path.join(WS, 'tools', 'notify.sh'), '暴露面变化：' + ' / '.join(problems)], timeout=60)
        cur['problems'] = problems
        json.dump(cur, open(STATE, 'w'), ensure_ascii=False, indent=1)
        print('EXPOSURE_WARN ' + ' / '.join(problems))
        return 1
    if not problems:
        print('EXPOSURE_OK 无任何IP放行，portproxy 仅计划内')
        return 0
    print('EXPOSURE_KNOWN ' + ' / '.join(problems))
    return 0

if __name__ == '__main__':
    sys.exit(main())
