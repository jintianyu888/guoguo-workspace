#!/usr/bin/env bash
# 0800-todo-reminder.sh —— 07:45 推送 08:00 窗口待办（只在 pending 文件存在时发）
# 自测：DRY=1 bash tools/0800-todo-reminder.sh
set -uo pipefail
WS=/home/j/.openclaw/workspace
P="$WS/state/work/pending-0800.md"
[ -f "$P" ] || exit 0
BODY=$(head -c 900 "$P")
MSG=$(printf '%s\n\n%s' '【07:45 提醒】今天 08:00 重启窗口待办：' "$BODY")
DRYARG=""
[ "${DRY:-0}" = "1" ] && DRYARG="--dry-run"
openclaw message send --channel feishu -t "user:ou_74fec7bc81cc6ec6d2b4de1c0967923b" -m "$MSG" $DRYARG 2>&1 | tail -2