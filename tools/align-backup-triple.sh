#!/usr/bin/env bash
# align-backup-triple.sh —— 三地归档「并集拉齐」（只补不删）2026-10-03 补
set -u
LOG=/home/j/.openclaw/workspace/state/work/align-triple.log
DIRS='d e h'
T=$(mktemp)
for d in $DIRS; do ls /mnt/$d/openclaw-backups/*.tar.gz 2>/dev/null | xargs -n1 basename 2>/dev/null; done | sort -u > "$T"
echo "[$(date '+%F %T')] 并集文件数: $(wc -l < "$T")" >> "$LOG"
while read -r f; do
  [ -n "$f" ] || continue
  SRC=''
  for x in $DIRS; do [ -f "/mnt/$x/openclaw-backups/$f" ] && { SRC="/mnt/$x/openclaw-backups/$f"; break; }; done
  [ -n "$SRC" ] || continue
  for d in $DIRS; do
    if [ ! -f "/mnt/$d/openclaw-backups/$f" ]; then mkdir -p "/mnt/$d/openclaw-backups"; cp -p "$SRC" "/mnt/$d/openclaw-backups/" && echo "  → $d 补 $f" >> "$LOG"; fi
  done
done < "$T"
rm -f "$T"
for d in $DIRS; do echo "  $d: $(ls /mnt/$d/openclaw-backups/*.tar.gz 2>/dev/null | wc -l)" >> "$LOG"; done
echo "[$(date '+%F %T')] 结束" >> "$LOG"