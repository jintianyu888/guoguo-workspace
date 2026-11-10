#!/bin/bash
# 乐谱库 H 盘版本化快照：每日一个日期目录，硬链接增量，保留 14 天
set -u
SRC=/mnt/e/openclaw-store/scores
ROOT=/mnt/h/openclaw-store/scores
LOG=/home/j/.openclaw/workspace/state/scores-snapshot.log
KEEP=14
DATE=$(date +%Y%m%d)
mkdir -p "$ROOT"
if [ ! -d "$SRC" ]; then echo "$(date '+%F %T') ❌ 源目录不存在 $SRC" >>"$LOG"; exit 0; fi
PREV=$(ls -1d "$ROOT"/20*/ 2>/dev/null | sort | tail -1)
if [ -n "$PREV" ]; then
  rsync -a --delete --link-dest="$PREV" "$SRC/" "$ROOT/$DATE/" >>"$LOG" 2>&1
else
  rsync -a "$SRC/" "$ROOT/$DATE/" >>"$LOG" 2>&1
fi
S=$(find "$SRC" -type f 2>/dev/null | wc -l)
D=$(find "$ROOT/$DATE" -type f 2>/dev/null | wc -l)
SZ=$(du -sh "$ROOT/$DATE" 2>/dev/null | cut -f1)
if [ "$S" = "$D" ]; then echo "$(date '+%F %T') ✅ $DATE 文件 $D/$S 大小 $SZ" >>"$LOG"; else echo "$(date '+%F %T') ⚠️ $DATE 文件数不符 $D/$S" >>"$LOG"; fi
ls -1d "$ROOT"/20*/ 2>/dev/null | sort | head -n -"$KEEP" | while read -r d; do
  echo "$(date '+%F %T') 🗑 清理旧快照 $d" >>"$LOG"; rm -rf "$d"
done
exit 0
