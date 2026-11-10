#!/bin/bash
# disk-junk-inventory.sh —— DEHX 四盘无用文件清点（只读，不删）
OUT=/home/j/.openclaw/workspace/state/work/disk-junk-inventory.txt
: > "$OUT"
say(){ echo "$@" >> "$OUT"; }
say "== $(date '+%F %T') =="
for d in d e h x; do
  df -h /mnt/$d 2>/dev/null | tail -1 >> "$OUT"
done
say ""
say "-- 回收站/备份站 顶层大小 --"
for p in /mnt/d/openclaw-trash /mnt/e/openclaw-trash /mnt/h/openclaw-trash \
         /mnt/e/openclaw-store /mnt/h/openclaw-store /mnt/e/openclaw-cloud-backup \
         /mnt/e/wsl-backup /mnt/h/wsl-backup /mnt/x/wsl-backup /mnt/x/WSL; do
  [ -e "$p" ] && say "$(du -sh "$p" 2>/dev/null | cut -f1)\t$p"
done
say ""
say "-- 回收站内单项 (>1G) --"
for p in /mnt/d/openclaw-trash /mnt/e/openclaw-trash /mnt/h/openclaw-trash; do
  [ -d "$p" ] || continue
  du -sm "$p"/* 2>/dev/null | awk '$1>1024' | sort -rn | while read s dir; do say "$((s/1024))G\t$dir"; done
done
say ""
say "-- 残留/垃圾文件 (*.stale *.part *.tmp *.bak>7d, >100M) --"
for d in d e h x; do
  find /mnt/$d -maxdepth 4 -type f \( -name '*.stale' -o -name '*.part' -o -name '*.tmp' -o -name '*.crdownload' -o -name 'Thumbs.db' \) -size +100M 2>/dev/null \
    | while read f; do say "$(du -h "$f" 2>/dev/null | cut -f1)\t$f"; done
done
say ""
say "-- 备份归档 (按时间/大小) --"
ls -lh /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | awk '{print $5, $6, $7, $8, $9}' | tail -25 >> "$OUT"
say ""
say "-- 完成 $(date '+%T') --"
