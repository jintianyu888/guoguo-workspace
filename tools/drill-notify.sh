#!/usr/bin/env bash
# 备份恢复演练 + 起止通报(含预估时间)
W=/home/j/.openclaw/workspace
bash $W/tools/notify.sh "▶ 开始：备份恢复演练｜预计 2~5 分钟（抽最新归档做深度自检+解包演练）"
T0=$(date +%s)
OUT=$($W/tools/backup-drill.sh 2>&1); RC=$?
T1=$(date +%s); DUR=$((T1-T0))
TAIL=$(printf '%s\n' "$OUT" | tail -6)
bash $W/tools/notify.sh "✅ 结束：备份恢复演练｜用时 ${DUR}s｜rc=$RC
$TAIL"
