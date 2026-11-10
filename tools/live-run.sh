#!/usr/bin/env bash
# live-run.sh — 带 Windows 黑窗的实时进度执行器（2026-11-07 主公令）
# 用法: live-run.sh "<标题>" <命令...>
set -u
W=/home/j/.openclaw/workspace
title="${1:-任务}"; shift
[ $# -eq 0 ] && { echo "用法: live-run.sh <标题> <命令...>"; exit 64; }
mkdir -p "$W/state/work/live"
slug=job
LOG="$W/state/work/live/${slug}-$(date +%H%M%S).log"
winpath(){ wslpath -w "$1"; }
ST="$W/state/work/live/status-$slug.txt"; rm -f "$ST"
WP=$(winpath "$LOG"); WPS=$(winpath "$W/tools/live-tail.ps1"); WST=$(winpath "$ST")
cd /mnt/c 2>/dev/null || true
/mnt/c/Windows/System32/cmd.exe /c start "果果 · $title" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$WPS" -Log "$WP" -Title "$title" -Status "$WST" >/dev/null 2>&1
cd "$W"
echo "[$(date "+%F %T")] 开始：$title" >> "$LOG"
"$@" 2>&1 | while IFS= read -r line; do printf "[%s] %s\n" "$(date "+%F %T")" "$line" | tee -a "$LOG"; done
rc=${PIPESTATUS[0]}
if [ "$rc" -eq 0 ]; then echo "===DONE rc=0 $(date "+%F %T")" >> "$LOG"; else echo "===FAIL rc=$rc $(date "+%F %T")" >> "$LOG"; fi
exit "$rc"