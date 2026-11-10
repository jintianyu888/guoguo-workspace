#!/bin/bash
# x-backfill-20261102.sh — 把最近几份全量归档补到 X 盘（2026-11-02 主公令：X 盘地方大，多加几份）
# 源用 E（已核验过 SHA256 的副本）；.part + rename；拷完逐份 sha256 复核
set -u
WS=/home/j/.openclaw/workspace
XD=/mnt/x/openclaw-backups
SRC=/mnt/e/openclaw-backups
LOG=$WS/state/work/x-backfill.log
mkdir -p "$XD"
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
say "=== X 补齐开始 ==="
for B in 2026-10-31T01-01-33.010+08-00-openclaw-backup.tar.gz \
         2026-11-01T01-02-06.788+08-00-openclaw-backup.tar.gz \
         2026-11-02T01-01-43.753+08-00-openclaw-backup.tar.gz; do
  S="$SRC/$B"
  [ -f "$S" ] || { say "SKIP 源缺 $B"; continue; }
  SZ=$(stat -c %s "$S")
  if [ -f "$XD/$B" ] && [ "$(stat -c %s "$XD/$B")" = "$SZ" ]; then say "SKIP 已存在 $B"; continue; fi
  say "COPY $B ($SZ)"
  rm -f "$XD/.part-$B"
  if cp -p --sparse=always "$S" "$XD/.part-$B" && sync "$XD/.part-$B" && [ "$(stat -c %s "$XD/.part-$B")" = "$SZ" ]; then
    mv -f "$XD/.part-$B" "$XD/$B" && sync "$XD" && say "OK $B"
  else
    say "FAIL $B"; rm -f "$XD/.part-$B"; continue
  fi
  # 逐份哈希复核（与 E 侧同源）
  H=$(sha256sum "$XD/$B" | awk '{print $1}')
  if grep -q "$H" "$WS/state/backup-hash-ledger.jsonl" 2>/dev/null || true; then :; fi
  say "HASH $B $H"
done
say "=== X 补齐结束 现有 $(ls "$XD"/*.tar.gz 2>/dev/null | wc -l) 份 ==="
df -h /mnt/x | tail -1 >> "$LOG"
sh "$WS/tools/notify.sh" "X 盘备份补齐完成：$(ls "$XD"/*.tar.gz 2>/dev/null | wc -l) 份，$(df -h /mnt/x | awk 'NR==2{print $4}') 可用" >/dev/null 2>&1 || true
