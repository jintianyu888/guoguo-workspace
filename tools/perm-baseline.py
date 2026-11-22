#!/usr/bin/env python3
"""perm-baseline.py —— 管家权限基线统一（2026-11-22 主公令：所有管家权限审核一遍）

做三件事，默认 dry-run，加 --apply 才写：
  A. exec.mode=ask → allowlist（ask 会在无人值守时挂起等审批，cron 必超时）
  B. 所有 allowlist 管家补齐基础文件操作：cp mv mkdir ls cat head tail grep stat
     （safeBins 与 safeBinProfiles 必须同时有，只加 safeBins 会被静默丢弃）
  C. 放开 deny 里的 file_write / dir_list（读写自己工作区）；file_fetch 保持拒（对外发文件仍要先批）
不动：rm、sudo、systemctl、secrets、gateway、nodes、browser、process、sessions_spawn

用法: python3 tools/perm-baseline.py [--apply]
"""
import json, os, shutil, subprocess, sys, time

CFG = '/home/j/.openclaw/openclaw.json'
CLI = '/home/j/.npm-global/bin/openclaw'
APPLY = '--apply' in sys.argv

CORE = ['cp', 'mv', 'mkdir', 'ls', 'cat', 'head', 'tail', 'grep', 'stat']
SYS = {b: '/usr/bin/' + b for b in CORE}
SYS['ls'] = '/usr/bin/ls'

d = json.load(open(CFG, encoding='utf-8'))
entries = d['agents']['entries']
plan = []

for aid, a in sorted(entries.items()):
    tools = a.setdefault('tools', {})
    ex = tools.setdefault('exec', {})
    mode = ex.get('mode') or ('denied' if 'exec' in (tools.get('deny') or []) else 'full')
    ch = []
    if mode == 'ask':
        ex['mode'] = 'allowlist'
        ch.append('ask→allowlist')
        mode = 'allowlist'
    if mode == 'allowlist':
        bins = [b for b in (ex.get('safeBins') or [])]
        profs = ex.setdefault('safeBinProfiles', {})
        added = []
        for name in CORE:
            p = SYS[name]
            if p not in bins and name not in [b.split('/')[-1] for b in bins]:
                bins.append(p); added.append(name)
            if name not in profs:
                profs[name] = {}
                if name not in added: added.append(name)
        # 去重保序
        seen, ded = set(), []
        for b in bins:
            if b not in seen:
                seen.add(b); ded.append(b)
        if ded != (ex.get('safeBins') or []):
            ex['safeBins'] = ded
        if added:
            ch.append('加文件命令:' + ','.join(added))
    deny = tools.get('deny') or []
    drop = [x for x in ('file_write', 'dir_list') if x in deny]
    if drop:
        tools['deny'] = [x for x in deny if x not in drop]
        ch.append('放开' + ','.join(drop))
    if ch:
        plan.append((aid, ch))

print(f'共 {len(entries)} 个管家，需改动 {len(plan)} 个')
for aid, ch in plan:
    print(f'  {aid:18} {"; ".join(ch)}')

if not APPLY:
    print('\n[dry-run] 加 --apply 写盘')
    sys.exit(0)

bak = CFG + '.bak-perm-' + time.strftime('%Y%m%d-%H%M%S')
shutil.copy2(CFG, bak)
patch = {'agents': {'entries': {aid: {'tools': {'exec': entries[aid]['tools'].get('exec', {}),
                                              'deny': entries[aid]['tools'].get('deny', [])}}
                              for aid, _ in plan}}}
open('/tmp/perm-baseline-patch.json', 'w', encoding='utf-8').write(json.dumps(patch, ensure_ascii=False))
r = subprocess.run([CLI, 'config', 'patch', '--stdin'], stdin=open('/tmp/perm-baseline-patch.json'),
                   capture_output=True, text=True)
print(r.stdout.strip()[-400:] or r.stderr.strip()[-400:])
print('备份:', bak)
