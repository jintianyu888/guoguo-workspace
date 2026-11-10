#!/bin/bash
# watch-cloud-backup-sync.sh —— 等 E→H cloud-backup 同步结束并飞书报结果
set -u
W=/home/j/.openclaw/workspace
while pgrep -f 'rsync.*openclaw-cloud-backup' >/dev/null 2>&1; do sleep 30; done
sleep 2
LOG=$W/state/work/cloud-backup-sync.log
RC=$(grep -o 'rc=[0-9]*' "$LOG" | tail -1 | cut -d= -f2)
E_N=$(find /mnt/e/openclaw-cloud-backup -type f 2>/dev/null | wc -l)
H_N=$(find /mnt/h/openclaw-cloud-backup -type f 2>/dev/null | wc -l)
H_SZ=$(du -sh /mnt/h/openclaw-cloud-backup 2>/dev/null | cut -f1)
if [ "$RC" = "0" ]; then
  bash "$W/tools/notify.sh" "✅ H盘 cloud-backup 同步完成｜E $E_N 个文件 / H $H_N 个文件 / 共 $H_SZ｜rc=0"
else
  bash "$W/tools/notify.sh" "❌ H盘 cloud-backup 同步异常｜rc=${RC:-未知}｜E $E_N / H $H_N｜日志 state/work/cloud-backup-sync.log"
fi
