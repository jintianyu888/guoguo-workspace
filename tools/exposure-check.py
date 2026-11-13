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
        raw = p.stdout
    except Exception:
        return ''
    # netsh 经 WSL interop 输出的是 UTF-8；按 gbk 解会把中文全变乱码，
    # '规则名称' 一条也匹配不到，findings 恒为空 -> 误报 EXPOSURE_OK（2026-11-13 修）
    for enc in ('utf-8', 'gbk'):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode('utf-8', 'ignore')

def parse_findings(text):
    """挑出"启用+入站+允许+远程IP=任意"的规则，并统计按端口命中的规则条数。"""
    findings = {}
    blocks = text.split('规则名称')
    scanned = max(0, len(blocks) - 1)
    seen = {p: 0 for p in PORTS}
    for block in blocks:
        hit = [p for p in PORTS if p in block]
        for p in hit:
            seen[p] += 1
        if not hit:
            continue
        name = '?'
        for _l in block.splitlines()[:3]:
            _l = _l.strip().lstrip(':').strip()
            if _l:
                name = _l
                break
        remote = direction = action = enabled = ''
        for line in block.splitlines():
            s = line.strip()
            if s.startswith('远程 IP'):
                remote = s.split(':', 1)[-1].strip()
            elif s.startswith('已启用'):
                enabled = s.split(':', 1)[-1].strip()
            elif s.startswith('方向'):
                direction = s.split(':', 1)[-1].strip()
            elif s.startswith('操作'):
                action = s.split(':', 1)[-1].strip()
        # 只有明确读到"任何/Any"才算放行；读不到（空）记为未知，不误报
        if remote not in ('任何', 'Any'):
            continue
        if direction and direction not in ('入', '入站', 'In', 'Inbound'):
            continue
        if action and action not in ('允许', 'Allow'):
            continue
        if enabled and enabled not in ('是', 'Yes'):
            continue
        findings[name] = remote
    return findings, scanned, seen


def firewall_ports():
    out = run([NETSH, 'advfirewall', 'firewall', 'show', 'rule', 'name=all', 'verbose'])
    return parse_findings(out)

def portproxy():
    out = run([NETSH, 'interface', 'portproxy', 'show', 'v4tov4'])
    rows = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[1].isdigit():
            rows.append('%s:%s -> %s:%s' % tuple(parts))
    return sorted(rows)

def main():
    if '--selftest' in sys.argv:
        return selftest()
    fw, scanned, seen = firewall_ports()
    pp = portproxy()
    cur = {'ts': time.strftime('%Y-%m-%d %H:%M:%S'), 'rules_scanned': scanned,
           'firewall_open_any': fw, 'ports_with_rules': seen, 'portproxy': pp}
    if scanned == 0:
        print('EXPOSURE_UNKNOWN 防火墙规则一条都没读到（提权/编码问题），不能当作已受控')
        return 2
    prev = {}
    if os.path.exists(STATE):
        try: prev = json.load(open(STATE))
        except Exception: prev = {}
    problems = []
    if fw:
        problems.append('防火墙仍有任何IP放行：' + '；'.join('%s(远程IP=%s)' % (k, v) for k, v in fw.items()))
    # WSL IP 每次重启都会变，别写死目标 IP；只按"监听 0.0.0.0 + 计划内端口"判断
    extra = [p for p in pp if not any(p.startswith('0.0.0.0:%s -> ' % port) for port in PORTS)]
    if extra:
        problems.append('出现计划外 portproxy：' + '；'.join(extra))
    json.dump(cur, open(STATE, 'w'), ensure_ascii=False, indent=1)
    if problems and problems != prev.get('problems'):
        subprocess.run(['bash', os.path.join(WS, 'tools', 'notify.sh'), '暴露面变化：' + ' / '.join(problems)], timeout=60)
        cur['problems'] = problems
        json.dump(cur, open(STATE, 'w'), ensure_ascii=False, indent=1)
        print('EXPOSURE_WARN ' + ' / '.join(problems))
        return 1
    gaps = ['%s 无专属防火墙规则（现由 svchost 宽口径规则顺带放行）' % p
            for p in PORTS if not seen.get(p)]
    if gaps:
        print('NOTE 已知缺口：' + '；'.join(gaps))
    if not problems:
        print('EXPOSURE_OK %d 条规则已扫，无任何IP放行，portproxy 仅计划内' % scanned)
        return 0
    print('EXPOSURE_KNOWN ' + ' / '.join(problems))
    return 0

SELFTEST_TEXT = """规则名称:                             test-open-any
----------------------------------------------------------------------
已启用:                                 是
方向:                                   入
操作:                                   允许
本地端口:                               18789
远程 IP:                                任何
规则名称:                             oc-9443
----------------------------------------------------------------------
已启用:                                 是
方向:                                   入
操作:                                   允许
本地端口:                               9443
远程 IP:                                100.64.0.0/10
规则名称:                             test-blocked
----------------------------------------------------------------------
已启用:                                 是
方向:                                   入
操作:                                   阻止
本地端口:                               18789
远程 IP:                                任何
"""


def selftest():
    ok = True
    fw, scanned, seen = parse_findings(SELFTEST_TEXT)
    checks = [
        ('扫描到 3 条规则', scanned == 3),
        ('任何IP放行被识别', 'test-open-any' in fw),
        ('tailnet 定向规则不误报', 'oc-9443' not in fw),
        ('阻止规则不误报', 'test-blocked' not in fw),
        ('18789 命中 2 条', seen['18789'] == 2),
        ('9443 命中 1 条', seen['9443'] == 1),
        ('空输出判为未读到', parse_findings('')[1] == 0),
    ]
    for nm, cond in checks:
        if not cond:
            ok = False
            print('SELFTEST_FAIL ' + nm)
    print('SELFTEST_OK' if ok else 'SELFTEST_FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
