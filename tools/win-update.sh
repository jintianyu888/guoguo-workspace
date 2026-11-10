#!/bin/bash
# win-update.sh — 月度 Windows 软件批量升级（winget）
# 用法: win-update.sh [--dry-run]
set -uo pipefail
WS="$HOME/.openclaw/workspace"
OUT="$WS/state/win-update"; mkdir -p "$OUT"
LOG="$OUT/$(date +%Y%m%d-%H%M).log"
LOCK="$WS/state/work/win-update.lock"; mkdir -p "$(dirname "$LOCK")"
PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1

exec 9>"$LOCK"
flock -n 9 || { echo "already running"; exit 3; }

say(){ echo "$*" | tee -a "$LOG"; }
runps(){ "$PS" -NoProfile -Command "$1" 2>&1 | tr -d "\r"; }

say "=== winget 升级 $(date '+%F %T') dry=$DRY ==="
VER=$(runps "winget --version")
say "winget: ${VER:-NOT_FOUND}"
if [ -z "$VER" ]; then say "RESULT=NO_WINGET"; exit 4; fi

say "--- 升级前可用更新 ---"
BEFORE=$(runps "winget upgrade --include-unknown --accept-source-agreements --disable-interactivity")
echo "$BEFORE" >> "$LOG"
CNT=$(printf "%s\n" "$BEFORE" | grep -cE -- "->" || true)
say "可用更新条数: $CNT"

if [ "$DRY" = "1" ]; then say "RESULT=DRY_RUN cnt=$CNT"; exit 0; fi
if [ "$CNT" -eq 0 ]; then say "RESULT=NO_UPDATE"; exit 0; fi

say "--- 执行升级 ---"
runps "winget upgrade --all --include-unknown --silent --accept-package-agreements --accept-source-agreements --disable-interactivity" >> "$LOG" 2>&1
RC=$?
say "upgrade rc=$RC"

say "--- 升级后剩余 ---"
AFTER=$(runps "winget upgrade --include-unknown --accept-source-agreements --disable-interactivity")
echo "$AFTER" >> "$LOG"
LEFT=$(printf "%s\n" "$AFTER" | grep -cE -- "->" || true)
say "RESULT=rc=$RC before=$CNT after=$LEFT"

MSG="Windows 软件月度升级｜更新前 $CNT 项，剩 $LEFT 项（rc=$RC）"
bash "$WS/tools/notify.sh" "$MSG" >/dev/null 2>&1 || true
exit 0
