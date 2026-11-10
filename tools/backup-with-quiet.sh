#!/usr/bin/env bash
# backup-with-quiet.sh —— 备份前暂停非紧急任务，结束后无条件恢复
set -uo pipefail
WS=/home/j/.openclaw/workspace
if [ $# -lt 1 ]; then echo "用法: $0 <命令...>"; exit 2; fi
python3 "$WS/tools/backup-quiet.py" pause || {
  echo "[quiet] 暂停失败，继续备份"
  bash "$WS/tools/notify.sh" "⚠️ 备份静默 pause 失败，本次备份将在无静默下运行（IO 可能紧张），请检查 openclaw cron 命令是否正常" || true
}
trap 'python3 "$WS/tools/backup-quiet.py" resume || true' EXIT INT TERM
"$@"
rc=$?
echo "[quiet] 备份退出码=$rc"
exit $rc
