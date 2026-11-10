#!/usr/bin/env bash
# score-notify.sh —— 乐谱库有变更就输出（供 announce 到飞书）；无变更静默退出
set -u
PEND=/home/j/.openclaw/workspace/state/work/score-intake-pending.txt
[ -s "$PEND" ] || exit 0
cat "$PEND"
: > "$PEND"