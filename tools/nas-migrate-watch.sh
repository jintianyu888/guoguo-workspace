#!/bin/bash
# nas-migrate-watch.sh —— 等迁移单元结束，统计结果并通知
set -uo pipefail
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/nas-migrate.log
UNIT=nas-migrate-20261102b
while systemctl --user is-active --quiet "$UNIT"; do sleep 60; done
sleep 5
{
  echo "$(date '+%F %T') === 迁移结束汇总 ==="
  tail -4 "$LOG"
  echo "目标目录文件数: $(ls -1 /mnt/nas/archive/jinyu/openclaw-archives/*.tar.gz 2>/dev/null | wc -l)"
  echo "目标目录大小: $(du -sh /mnt/nas/archive/jinyu/openclaw-archives 2>/dev/null | awk '{print $1}')"
  df -h /mnt/nas | tail -1
} >> "$LOG"
MSG="老NAS→新NAS 归档迁移结束：$(grep -c '^.* OK ' "$LOG" 2>/dev/null || echo 0) 份成功。$(tail -1 "$LOG")"
timeout 60 bash "$WS/tools/notify.sh" "$MSG" >/dev/null 2>&1 || true
touch "$WS/state/work/nas-migrate.done"
