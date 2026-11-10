#!/bin/bash
# update-repair-run.sh —— 在网关进程树之外执行 openclaw update repair（doctor 拒绝在树内跑）
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/work/update-repair.log
echo "=== $(date "+%F %T") repair 开始（脱离网关进程树）===" >> "$LOG"
openclaw update repair --no-restart >> "$LOG" 2>&1
RC=$?
echo "=== $(date "+%F %T") repair 结束 rc=$RC ===" >> "$LOG"
MSGT="update repair 完成 rc=$RC"
[ "$RC" != "0" ] && MSGT="⚠️ update repair 失败 rc=$RC，日志 state/work/update-repair.log"
timeout 60 bash "$W/tools/notify.sh" "$MSGT" >/dev/null 2>&1 || true
exit $RC
