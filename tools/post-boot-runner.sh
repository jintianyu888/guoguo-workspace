#!/bin/bash
# post-boot-runner.sh v1.0 (2026-11-17) —— 开机一次性任务执行器
# 约定：把要做的事写进 state/work/post-boot.sh，开机自愈时执行一次，然后改名归档。
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/log/post-boot.log
PB=$W/state/work/post-boot.sh
mkdir -p "$(dirname "$LOG")"
say(){ echo "[$(date '+%F %T')] $*" >>"$LOG"; }
[ -f "$PB" ] || { say "无 post-boot.sh，跳过"; exit 0; }
say "=== 执行 post-boot.sh ==="
bash "$PB" >>"$LOG" 2>&1
RC=$?
say "=== post-boot.sh 结束 rc=$RC ==="
mv "$PB" "$PB.done-$(date +%Y%m%d-%H%M%S)"
bash "$W/tools/notify.sh" "【开机一次性任务】post-boot.sh 已执行 rc=$RC，详情 state/log/post-boot.log" >/dev/null 2>&1 || true
exit 0
