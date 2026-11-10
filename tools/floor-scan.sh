#!/bin/bash
cd /home/j/.openclaw/workspace
F=state/work/floor-scan.txt
{
echo "=== 生成于 $(date '+%F %T') ==="
echo "--- D 备份清单 ---"
ls -l --time-style=+%F_%H:%M /mnt/d/openclaw-backups 2>/dev/null | grep 'tar.gz' | awk '{print $5, $6, $7}'
echo "--- 各目录体量 ---"
for d in /mnt/e/openclaw-backups /mnt/e/openclaw-store /mnt/e/openclaw-trash /mnt/e/openclaw-cloud-backup /mnt/e/wsl-backup /mnt/h/openclaw-backups /mnt/h/openclaw-store /mnt/h/openclaw-trash /mnt/h/wsl-backup /mnt/h/openclaw-cloud-backup; do
  s=$(timeout 300 du -sm "$d" 2>/dev/null | cut -f1)
  echo "$d|${s:-TIMEOUT}"
done
echo "--- E/H trash 明细(前20大) ---"
timeout 200 du -sm /mnt/e/openclaw-trash/* 2>/dev/null | sort -rn | head -20
timeout 200 du -sm /mnt/h/openclaw-trash/* 2>/dev/null | sort -rn | head -20
echo "=== 完成 $(date '+%F %T') ==="
} > $F 2>&1

