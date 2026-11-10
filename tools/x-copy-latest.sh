#!/bin/bash
# x-copy-latest.sh — 把最新归档复制到 X 正式备份层（2026-10-30 双审定稿 zhipu+minimax）
# 修正落实：gzip -t 完整性门禁；.part+rename；同名跳过；孤儿检测告警；flock 防并发；只数 *.tar.gz
set -u
WS=/home/j/.openclaw/workspace
XD=/mnt/x/openclaw-backups
LOG=$WS/state/work/x-copy.log
KEEP_X=$(grep -E '^KEEP_X=[0-9]' "$WS/tools/retention.env" 2>/dev/null | head -1 | grep -oE '[0-9]+' | head -1)
if [ -z "$KEEP_X" ]; then KEEP_X=2; fi
mkdir -p "$XD"
exec 9>/run/user/$(id -u)/x-copy.lock
flock -n 9 || { echo "[$(date '+%F %T')] 已有实例在跑，跳过" >> "$LOG"; exit 0; }
SRC=$(ls -t /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | head -1)
if [ -z "$SRC" ]; then echo "[$(date '+%F %T')] D 盘无归档" >> "$LOG"; exit 1; fi
B=$(basename "$SRC")
SZ=$(stat -c %s "$SRC" 2>/dev/null)
if [ -f "$XD/$B" ]; then
  echo "[$(date '+%F %T')] $B 已在 X，跳过复制" >> "$LOG"
elif gzip -t "$SRC" 2>>"$LOG"; then
  echo "[$(date '+%F %T')] 完整性 OK，开始复制 $B（$SZ 字节）" >> "$LOG"
  if cp -p "$SRC" "$XD/.part-$B"; then
    if mv "$XD/.part-$B" "$XD/$B"; then
      echo "[$(date '+%F %T')] X 复制完成 $B" >> "$LOG"
    else
      echo "[$(date '+%F %T')] X rename 失败（.part 保留排查）" >> "$LOG"; exit 1
    fi
  else
    echo "[$(date '+%F %T')] X 复制失败（.part 保留排查）" >> "$LOG"; exit 1
  fi
else
  echo "[$(date '+%F %T')] $B gzip 校验失败，拒绝复制到 X" >> "$LOG"; exit 1
fi
for f in "$XD"/*.tar.gz; do
  if [ -e "$f" ]; then
    b=$(basename "$f")
    s=$(stat -c %s "$f")
    ok=0
    for d in /mnt/e/openclaw-backups /mnt/h/openclaw-backups; do
      if [ -f "$d/$b" ] && [ "$(stat -c %s "$d/$b" 2>/dev/null)" = "$s" ]; then ok=1; fi
    done
    if [ "$ok" = 0 ]; then echo "[$(date '+%F %T')] WARN 孤儿包: $b（$s 字节，E/H 无同名同大小副本）" >> "$LOG"; fi
  fi
done
DF=$(df -h /mnt/x | awk 'NR==2{print $5}')
if [ -z "$DF" ]; then DF=未知; fi
echo "[$(date '+%F %T')] 汇总 X=$(ls "$XD"/*.tar.gz 2>/dev/null | wc -l) 份(KEEP_X=$KEEP_X)，X盘 $DF" >> "$LOG"
