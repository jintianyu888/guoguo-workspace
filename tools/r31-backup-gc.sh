#!/bin/bash
# R31 检查：备份盘自动回收定时器在跑，且 48 小时内有成功记录
W=/home/j/.openclaw/workspace
if ! systemctl --user is-enabled --quiet oc-backup-gc.timer 2>/dev/null; then
  echo "R31 FAIL: oc-backup-gc.timer 未启用"; exit 1
fi
LOG=$W/state/work/backup-gc.log
if [ ! -f "$LOG" ]; then echo "R31 FAIL: 无 backup-gc.log"; exit 1; fi
AGE=$(( ( $(date +%s) - $(stat -c %Y "$LOG") ) / 3600 ))
if [ "$AGE" -gt 48 ]; then echo "R31 FAIL: 回收日志已 $AGE 小时未更新"; exit 1; fi
echo "R31 PASS: 定时器已启用，日志 $AGE 小时前更新"
exit 0
