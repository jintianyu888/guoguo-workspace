#!/bin/bash
# 等待首个快照 rsync 结束 → 核对文件数 → 飞书通知
set -u
W=/home/j/.openclaw/workspace
SNAP=/mnt/h/openclaw-store/scores/20261017
SRC=/mnt/e/openclaw-store/scores
n=0
while pgrep -f "rsync .*$SRC/" >/dev/null && [ $n -lt 45 ]; do sleep 20; n=$((n+1)); done
S=$(find "$SRC" -type f 2>/dev/null | wc -l)
D=$(find "$SNAP" -type f 2>/dev/null | wc -l)
SZ=$(du -sh "$SNAP" 2>/dev/null | cut -f1)
echo "$(date '+%F %T') verify src=$S dst=$D size=$SZ" >> "$W/state/scores-snapshot.log"
if [ "$S" = "$D" ] && [ "$D" -gt 0 ]; then
  bash "$W/tools/notify.sh" "✅ 乐谱库 H 盘首份快照完成：$D/$S 文件，$SZ"
else
  bash "$W/tools/notify.sh" "⚠️ 乐谱库快照文件数不符：$D/$S（$SZ），待查"
fi
