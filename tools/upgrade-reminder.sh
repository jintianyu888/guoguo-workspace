#!/bin/bash
# 提醒：2026-11-24 检查 OpenClaw 11.5 是否满 7 天并执行升级评估
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
W=/home/j/.openclaw/workspace
cd "$W" || exit 3
CUR=$(openclaw --version 2>/dev/null | tail -1)
LATEST=$(timeout 60 npm view openclaw version 2>/dev/null | tail -1)
PUB=$(timeout 60 npm view openclaw time --json 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print((d.get('$LATEST') or '')[:10])" 2>/dev/null)
bash tools/notify.sh "【升级到点】任务#1020：当前 $CUR，npm 最新 $LATEST（$PUB）。若已满7天且非beta，今天适合走 tools/upgrade-panel.sh 升级；未满则顺延。" >/dev/null 2>&1 || true
echo "$(date '+%F %T') cur=$CUR latest=$LATEST pub=$PUB" >> state/work/upgrade-reminder.log
exit 0