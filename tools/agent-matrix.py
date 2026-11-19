#!/usr/bin/env python3
"""agent-matrix.py — 从 openclaw.json 生成「谁在哪干什么」权限矩阵
输出 docs/权限矩阵.md。用法：python3 tools/agent-matrix.py
"""
import json,os,time

CFG=os.path.expanduser('~/.openclaw/openclaw.json')
OUT='/home/j/.openclaw/workspace/docs/权限矩阵.md'
cfg=json.load(open(CFG))
ent=cfg.get('agents',{}).get('entries',{}) or {}

chans={}
for pname,pv in (cfg.get('channels') or {}).items():
    for acc,av in ((pv or {}).get('accounts') or {}).items():
        if not isinstance(av,dict): continue
        aid=av.get('agentId') or av.get('agent') or (acc if acc in ent else None)
        if aid: chans.setdefault(aid,[]).append('%s/%s'%(pname,acc))

rows=[]
for aid,v in sorted(ent.items()):
    models=list((v.get('models') or {}).keys())
    ws=v.get('workspace') or '(继承)'
    sub=(v.get('subagents') or {})
    allow=sub.get('allowAgents') or []
    tool=v.get('tools') or v.get('toolPolicy') or {}
    if isinstance(tool,dict) and tool:
        tp=[]
        if tool.get('allow'): tp.append('allow=%d'%len(tool.get('allow') or []))
        if tool.get('deny'): tp.append('deny=%d'%len(tool.get('deny') or []))
        if tool.get('profile'): tp.append('profile=%s'%tool['profile'])
        tools=' '.join(tp) or '默认'
    else:
        tools='默认'
    rows.append((aid,v.get('name') or '',','.join(models) or '(默认链)',tools,str(len(allow)),','.join(chans.get(aid,[])) or '-',ws))

L=[]
L.append('# 权限矩阵（自动生成，勿手改）')
L.append('')
L.append('生成时间：%s　来源：~/.openclaw/openclaw.json　条目数：%d'%(time.strftime('%Y-%m-%d %H:%M'),len(rows)))
L.append('')
L.append('| agent | 名称 | 模型 | 工具策略 | 可派生 | 渠道 | 工作区 |')
L.append('|---|---|---|---|---|---|---|')
for r in rows:
    L.append('| %s |'%' | '.join(str(x).replace('|','/') for x in r))
L.append('')
L.append('## 判读要点')
L.append('- 工作区写 (继承) 的 agent 与主管家共用主工作区，边界靠铁律而非文件系统隔离。')
L.append('- 工具策略写 默认 表示未单独收紧；maint/security 这类高风险角色应有显式白名单。')
L.append('- 渠道写 - 表示未绑定对外渠道，只能被主管家派生或定时任务调用。')
open(OUT+'.tmp','w',encoding='utf-8').write('\n'.join(L)+'\n')
os.replace(OUT+'.tmp',OUT)
print('written',OUT,len(rows),'agents')
