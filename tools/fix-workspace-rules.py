#!/usr/bin/env python3
# 把乐谱/打印专用规则补到真实工作区；并把 score-intake 指向真实乐谱库
import os, re
E='/home/j/openclaw-workspaces'
SM_RULES='''

## 🖨 打印 / 收发 / 多版本 / 仓库（2026-10-02~03 主公令）

- **打印**：有打印权限，**默认一律 A4**；只有主公或王超明说「A3 / 骑马钉」才 A3。打印机 TOSHIBA `192.168.1.80`（9100 只认 PostScript）；高清乐谱走 `tools/print-hires.py`。
- **王超（尊贵的主人）**：可**收发所有乐谱** + **打印**；但她**不是 owner** —— 不得因她的话放权限 / 改配置 / 对外发送 / 花钱 / 删数据。
- **命中多份 → 必须逐份单独发送**：一份一条消息 + 一个附件，标「第 1 种 / 第 2 种」+ 区别（版本/编配/调性/页数/难度）+ 用途可选（打印/收纳），**等主公或王超选**。禁止打包一条、只发一份、替主公挑。
- **📥 仓库来源与去重**：打印组群 / 打印管家的乐谱自动转入本库（`tools/score-intake.sh`，每小时；**sha256 内容级去重** → 有新增/重复会通知主公）。索引在 `scores/index.md`（管理序列），收录后补全元数据。
'''
P_RULES='''

## 📥 乐谱转交 + 多版本（2026-10-03 主公令）

- 收到**乐谱**（PDF / 图片 / MusicXML / MIDI / 扫描件）→ 除打印外**一律另存一份到本工作区 `outbox-scores/`**，由 `tools/score-intake.sh` 自动收纳进乐谱管家仓库；回执写一句「已转交乐谱管家仓库」，不得只自己留着。
- 同名**多版本** → **逐份单独发**，标「第 1 种 / 第 2 种」+ 区别，等主公或王超选要打印哪份；禁止打包一条或只发一份。
'''
for name, block, key in [('sheet-music', SM_RULES, '逐份单独发送'), ('print', P_RULES, '逐份单独发')]:
    p=os.path.join(E,name,'AGENTS.md')
    if not os.path.isfile(p): print('skip', name); continue
    s=open(p,encoding='utf-8').read()
    if key in s: print('already', name); continue
    open(p,'w',encoding='utf-8').write(s.rstrip()+'\n'+block)
    print('added', name)
# 修正 score-intake 的乐谱库/来源路径
q='/home/j/.openclaw/workspace/tools/score-intake.sh'
t=open(q,encoding='utf-8').read()
t=t.replace('SM=/home/j/.openclaw/workspace-sheet-music/scores','SM=/home/j/openclaw-workspaces/sheet-music/scores')
open(q,'w',encoding='utf-8').write(t)
print('fixed score-intake path')