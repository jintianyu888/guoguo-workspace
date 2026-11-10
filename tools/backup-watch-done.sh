#!/bin/bash
# backup-watch-done.sh —— 只读看门狗：等全量备份进程结束后，核对是否生成新归档并通过飞书汇报
# 用法: backup-watch-done.sh <开始时间戳epoch>
set -u
W=/home/j/.openclaw/workspace
START=${1:-$(date +%s)}
LOG=$W/state/work/backup-watch.log
echo "[$(date '+%F %T')] watch start (since $START)" >> "$LOG"
while pgrep -f 'nas-push-archive.sh create' >/dev/null 2>&1; do sleep 60; done
END=$(date +%s)
MINS=$(( (END-START)/60 ))
NEW=$(ls -t /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | head -1)
if [ -n "$NEW" ]; then
  MT=$(stat -c %Y "$NEW" 2>/dev/null || echo 0)
  SZ=$(du -h "$NEW" 2>/dev/null | awk '{print $1}')
  if [ "$MT" -ge "$START" ]; then
    MSG="✅ 全量备份完成：$(basename "$NEW") 大小 $SZ，耗时约 ${MINS} 分钟（本地 D 盘）"
  else
    MSG="⚠️ 全量备份进程已结束，但没发现新归档（最新仍是 $(basename "$NEW")，$SZ），耗时 ${MINS} 分钟，需排查"
  fi
else
  MSG="⚠️ 全量备份进程已结束，备份目录里没有归档文件，需排查（耗时 ${MINS} 分钟）"
fi
echo "[$(date '+%F %T')] $MSG" >> "$LOG"
bash "$W/tools/notify.sh" "$MSG" >> "$LOG" 2>&1