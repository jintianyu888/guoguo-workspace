#!/bin/bash
# peer-review-init.sh v1.0 — 互审目录与轮次脚手架（零 token）
set -uo pipefail
D=$(date +%F); W=/home/j/.openclaw/workspace
mkdir -p $W/state/butler/review/$D
declare -A WS=( [main]=$W [maint]=/home/j/openclaw-workspaces/maint [backup]=/home/j/.openclaw/workspace-backup [model]=/home/j/.openclaw/workspace-model [work]=/home/j/openclaw-workspaces/work [hermess]=/home/j/openclaw-workspaces/sheet-music )
for k in "${!WS[@]}"; do mkdir -p "${WS[$k]}/state/reports"; done
echo "$D init ok"
# 轮次台账：记录各家当天进度
python3 - <<'PY'
import json,os,datetime
W='/home/j/.openclaw/workspace'; D=datetime.date.today().isoformat()
WS={'main':W,'maint':'/home/j/openclaw-workspaces/maint','backup':'/home/j/.openclaw/workspace-backup','model':'/home/j/.openclaw/workspace-model','work':'/home/j/openclaw-workspaces/work','hermess':'/home/j/openclaw-workspaces/sheet-music'}
PAIR={'main':'hermess','hermess':'main','maint':'backup','backup':'maint','model':'work','work':'model'}
rows={}
for k,root in WS.items():
    has=lambda n: os.path.exists(f'{root}/state/reports/{n}-{D}.md')
    stage='1-起草' if has('draft') else '0-未开始'
    if has('review'): stage='2-已审'
    if has('revised'): stage='3-已修订'
    if has('final'): stage='4-定稿'
    rows[k]={'peer':PAIR[k],'stage':stage,'draft':has('draft'),'review':has('review'),'revised':has('revised'),'final':has('final')}
json.dump({'date':D,'rows':rows},open(f'{W}/state/butler/review/{D}/status.json','w'),ensure_ascii=False,indent=1)
for k,v in rows.items(): print(k,v['stage'],'审理方',v['peer'])
PY
