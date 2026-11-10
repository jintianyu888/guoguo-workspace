#!/usr/bin/env python3
# 2026-10-02 主公令：除 main 外所有管家去掉页尾；统一称王超「尊贵的主人」
import re, glob, os, shutil
BASE='/home/j/.openclaw'
SKIP={'workspace'}
NEW_FOOTER='## 不写页脚（2026-10-02 主公令）\n\n- **不要附任何页脚 / 页尾**（余额、token 花费、时段、主机、缓存等一律不写）。\n'
ZUN='\n## 👑 称呼规矩（2026-10-02 主公令）\n\n- **对王超说话时**：回话**开头必须加前缀「尊贵的主人」**；平时称呼也用「主人」。\n'
changed=[]
for d in sorted(glob.glob(BASE+'/workspace*')):
    if not os.path.isdir(d): continue
    if os.path.basename(d) in SKIP: continue
    p=os.path.join(d,'AGENTS.md')
    if not os.path.isfile(p): continue
    s=open(p,encoding='utf-8').read(); o=s
    shutil.copy2(p, p+'.bak-20261002')
    s=re.sub(r'##\s*回复页脚规范[^\n]*\n(?:.*\n)*?(?=##|\Z)', NEW_FOOTER+'\n', s)
    s=re.sub(r'^\s*-\s*\*\*页脚[^\n]*\n', '', s, flags=re.M)
    if '尊贵的主人' not in s: s=s.rstrip()+'\n'+ZUN
    if s!=o:
        open(p,'w',encoding='utf-8').write(s); changed.append(os.path.basename(d))
print('changed', len(changed));
for c in changed: print(' -', c)