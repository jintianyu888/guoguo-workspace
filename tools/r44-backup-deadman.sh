#!/bin/bash
# r44-backup-deadman.sh —— R44：备份/巡检必须有独立 deadman，且 45 分钟内能发现静默失效
set -uo pipefail
W=/home/j/.openclaw/workspace
ok=1
for t in oc-deadman.timer oc-state-backup.timer oc-state-push.timer; do
  if ! systemctl --user is-active --quiet "$t"; then echo "BAD $t 未运行"; ok=0; fi
done
OKF=/home/j/.openclaw/state/backups/.last-ok
if [ ! -f "$OKF" ]; then
  echo "BAD 快照心跳 .last-ok 不存在"; ok=0
else
  AGE=$(( ($(date +%s) - $(cat "$OKF" 2>/dev/null || echo 0)) / 60 ))
  if [ "$AGE" -gt 45 ]; then echo "BAD 快照心跳 $AGE 分钟未更新（RPO 15 分钟已破）"; ok=0; fi
fi
LAST=$(ls -1t /mnt/d/oc-state-backups/openclaw-*.sqlite 2>/dev/null | head -1)
if [ -z "$LAST" ]; then echo "BAD /mnt/d 无 state 异盘快照"; ok=0; fi
[ "$ok" = 1 ] && echo "GREEN 备份链路与 deadman 正常（R44）"
exit $((1-ok))
