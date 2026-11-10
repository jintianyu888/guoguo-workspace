#!/bin/bash
# storage-inspect-cron.sh —— 两条只读巡检（默认只打印，不执行）
# 用法: storage-inspect-cron.sh --apply
set -uo pipefail
APPLY=0; [ "${1:-}" = "--apply" ] && APPLY=1
CMD_X="bash ~/.openclaw/workspace/tools/wsl-disk-health.sh --quiet"
CMD_NAS="bash ~/.openclaw/workspace/tools/nas-free-check.sh"
run(){ echo "+ $*"; [ "$APPLY" = "1" ] && eval "$@"; }
run openclaw cron add --name "X盘体检(每日)" --cron "20 7 * * *" --tz Asia/Shanghai --command "$CMD_X" --announce --best-effort-deliver
run openclaw cron add --name "群晖容量巡检(每日)" --cron "25 7 * * *" --tz Asia/Shanghai --command "$CMD_NAS" --announce --best-effort-deliver
echo "（未加 --apply 时仅打印命令，不落库）"

