#!/bin/bash
# 等存储区快照跑完 → 校验 → 清理 H 盘工作区里的旧副本（仅在校验通过时）
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/store-snapshot.log
n=0
while pgrep -f "rsync .*openclaw-store" >/dev/null && [ $n -lt 60 ]; do sleep 20; n=$((n+1)); done
OK=1; MSG=""
for IT in cooking-videos script-mystery-media; do
  S=$(find /mnt/e/openclaw-store/$IT -type f 2>/dev/null | wc -l)
  D=$(find /mnt/h/openclaw-store/$IT/20261017 -type f 2>/dev/null | wc -l)
  if [ "$S" != "$D" ]; then OK=0; MSG="$MSG $IT=$D/$S"; fi
done
if [ "$OK" = "1" ]; then
  rm -rf /mnt/h/openclaw-workspaces/cooking/videos /mnt/h/openclaw-workspaces/script-mystery/media /mnt/h/openclaw-workspaces/sheet-music/scores
  echo "$(date "+%F %T") TIDY 已清理 H 盘旧副本，快照校验通过" >>"$LOG"
  bash "$W/tools/notify.sh" "EH 整理完成：存储区快照校验通过，H 盘工作区旧副本已清理"
else
  echo "$(date "+%F %T") TIDY 跳过清理，快照文件数不符:$MSG" >>"$LOG"
  bash "$W/tools/notify.sh" "EH 整理：快照文件数不符，已跳过清理（$MSG）"
fi
exit 0