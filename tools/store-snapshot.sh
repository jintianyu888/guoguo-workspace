#!/bin/bash
# EH 存储区版本化快照：每个条目每日一个日期目录，硬链接增量，保留 14 天
set -u
# 2026-11-15: 互斥锁 + 起止标记。11-14 该脚本 03:24 跑完主体却挂住不退，
# 把网关拖了 5 小时，导致 03:47~06:50 十余个定时任务集体漏跑。
LOG=/home/j/.openclaw/workspace/state/store-snapshot.log
exec 9>/tmp/store-snapshot.lock
flock -n 9 || { echo "$(date '+%F %T') 已有实例在跑，退出" >>"$LOG"; exit 0; }
SRCROOT=/mnt/e/openclaw-store
ROOT=/mnt/h/openclaw-store
KEEP=14
DATE=$(date +%Y%m%d)
echo "$(date '+%F %T') START pid=$$" >>"$LOG"
ITEMS="scores cooking-videos script-mystery-media"
for IT in $ITEMS; do
  SRC="$SRCROOT/$IT"; OUT="$ROOT/$IT"
  [ -d "$SRC" ] || { echo "$(date '+%F %T') skip $IT (无源目录)" >>"$LOG"; continue; }
  mkdir -p "$OUT"
  if [ -d "$OUT/$DATE" ]; then echo "$(date '+%F %T') skip $IT $DATE (已存在)" >>"$LOG"; continue; fi
  PREV=$(ls -1d "$OUT"/20*/ 2>/dev/null | sort | tail -1)
  if [ -n "$PREV" ] && [ "$PREV" != "$OUT/$DATE/" ]; then
    rsync -a --delete --link-dest="$PREV" "$SRC/" "$OUT/$DATE/" >>"$LOG" 2>&1
  elif [ ! -d "$OUT/$DATE" ]; then
    rsync -a "$SRC/" "$OUT/$DATE/" >>"$LOG" 2>&1
  else
    rsync -a --link-dest="$OUT/$DATE" "$SRC/" "$OUT/$DATE.tmp/" >>"$LOG" 2>&1 && rm -rf "$OUT/$DATE" && mv "$OUT/$DATE.tmp" "$OUT/$DATE"
  fi
  S=$(find "$SRC" -type f 2>/dev/null | wc -l); D=$(find "$OUT/$DATE" -type f 2>/dev/null | wc -l)
  SZ=$(du -sh "$OUT/$DATE" 2>/dev/null | cut -f1)
  if [ "$S" = "$D" ]; then echo "$(date '+%F %T') ✅ $IT $DATE 文件 $D/$S 大小 $SZ" >>"$LOG"
  else echo "$(date '+%F %T') ⚠️ $IT $DATE 文件数不符 $D/$S" >>"$LOG"; fi
  touch "$OUT/$DATE/.snapshot-done"
  ls -1d "$OUT"/20*/ 2>/dev/null | sort | head -n -"$KEEP" | while read -r d; do rm -rf "$d"; echo "$(date '+%F %T') 🗑 $IT 清理 $d" >>"$LOG"; done
done
echo "$(date '+%F %T') END" >>"$LOG"
exit 0
