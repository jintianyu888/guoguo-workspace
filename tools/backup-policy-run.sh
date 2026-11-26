#!/bin/bash
# backup-policy-run.sh — 唯一备份策略执行入口
#  作用：dry-run 计划 / 补齐副本(SINK+冷档) / 自动删除(需 flag)
#  flag: state/work/backup-policy-allow-delete 存在才允许删除
set -uo pipefail
cd /home/j/.openclaw/workspace || exit 1
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
LK=state/work/backup-policy.lock
exec 9>"$LK"
flock -n 9 || { echo "$(date '+%F %T') SKIP 已有实例" >> state/work/backup-policy.log; exit 0; }
ARGS=(--repair)
if [ -f state/work/backup-policy-allow-delete ]; then
  ARGS+=(--apply)
fi
nice -n 12 ionice -c2 -n7 python3 tools/backup-policy.py "${ARGS[@]}" 2>&1
rc=$?
# 每次运行写一份快照给面板/巡检
python3 tools/backup-policy.py > "state/work/backup-policy-latest.txt" 2>&1 || true
exit $rc
