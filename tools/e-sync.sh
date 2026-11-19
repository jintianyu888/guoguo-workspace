#!/bin/bash
set -uo pipefail
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/e-sync.log
say(){ echo "$(date '+%F %T') $*" >> "$LOG"; }
tgt=/mnt/e/openclaw-backups
say "E 补齐开始 可用 $(( $(df -P "$tgt" | awk 'NR==2{print $4}') /1024/1024 ))G"
for n in 2026-10-18T13-09-20.879+08-00-openclaw-backup.tar.gz 2026-10-18T14-01-45.078+08-00-openclaw-backup.tar.gz; do
  src=/mnt/d/openclaw-backups/$n; dst=$tgt/$n
  if [ -f "$dst" ] && [ "$(stat -c%s "$dst")" = "$(stat -c%s "$src")" ]; then say "已有 $n"; continue; fi
  say "复制 -> $n"
  cp -f "$src" "$dst.part" || { say "失败 $n"; rm -f "$dst.part"; continue; }
  a=$(stat -c%s "$src"); b=$(stat -c%s "$dst.part")
  if [ "$a" = "$b" ]; then mv -f "$dst.part" "$dst"; say "已落位 $b"; else say "大小不符 $b/$a"; fi
done
say "E 补齐完成"
h=$(sha256sum "$tgt/2026-10-18T14-01-45.078+08-00-openclaw-backup.tar.gz" | awk '{print $1}'); say "E 最新份哈希 $h"
