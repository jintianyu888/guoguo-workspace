#!/usr/bin/env python3
"""asset-audit.py —— 技能/脚本 资产清单 + 变更比对（零 token）"""
import glob, os, hashlib, json
W = '/home/j/.openclaw/workspace'
B = W + '/state/.asset-baseline.json'
def h(p):
    try:
        return hashlib.md5(open(p, 'rb').read()).hexdigest()[:10]
    except Exception:
        return '-'
cur = {}
pats = ['/home/j/.openclaw/plugin-skills/*/SKILL.md',
        '/home/j/.openclaw/agents/*/agent/workshop-skills/*/SKILL.md',
        '/usr/local/node26/lib/node_modules/openclaw/skills/*/SKILL.md',
        '/usr/local/node26/lib/node_modules/openclaw/custodian-skills/*/SKILL.md']
for pat in pats:
    for p in glob.glob(pat):
        name = p.split('/SKILL.md')[0].split('/')[-1]
        cur['skill:' + name] = h(p)
for p in glob.glob(W + '/tools/*'):
    if os.path.isfile(p) and not p.endswith(('.log', '.pyc')):
        cur['tool:' + os.path.basename(p)] = h(p)
old = {}
try:
    old = json.load(open(B))
except Exception:
    pass
new = [k for k in cur if k not in old]
gone = [k for k in old if k not in cur]
chg = [k for k in cur if k in old and cur[k] != old[k]]
print('📦 资产清单 · %d 项（技能 %d · 脚本 %d）' % (len(cur), sum(1 for k in cur if k.startswith('skill:')), sum(1 for k in cur if k.startswith('tool:'))))
if old:
    print('🔍 与上次比对：新增 %d · 移除 %d · 变更 %d' % (len(new), len(gone), len(chg)))
    for k in new: print('   ➕', k)
    for k in chg: print('   ✏️', k)
    for k in gone: print('   ➖', k)
    if not (new or gone or chg): print('   ✅ 无变化')
else:
    print('（首次运行，已建立基线）')
json.dump(cur, open(B, 'w'))