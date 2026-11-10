#!/usr/bin/env bash
# notify-flush.sh — 重放静默窗期间入队的通知（P1 2026-10-26）
# 队列 state/notify-queue/*.json；失败进 dead/ 并 webhook 告警；队列保留 7 天
# 用法: bash tools/notify-flush.sh [--dry-run]
set -u
W=/home/j/.openclaw/workspace
Q=$W/state/notify-queue
DEAD=$Q/dead
LOG=$W/state/work/notify-flush.log
LOCK=$W/state/work/.notify-flush.lock
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
mkdir -p "$Q" "$DEAD"
log(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }
[ -f "$LOG" ] && [ $(stat -c %s "$LOG" 2>/dev/null || echo 0) -gt 1048576 ] && tail -c 512K "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"

exec 9>"$LOCK"
if ! flock -n 9; then log "SKIP 已有 flush 在跑"; exit 0; fi

SENT=0; FAIL=0
shopt -s nullglob
for f in "$Q"/*.json; do
  [ -f "$f" ] || continue
  # 7 天前的旧件直接进 dead（不重放，避免翻旧账）
  if [ -n "$(find "$f" -mtime +7 2>/dev/null)" ]; then
    mv -f "$f" "$DEAD/" 2>/dev/null && log "EXPIRE $(basename "$f")"
    continue
  fi
  MSG=$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1],encoding="utf-8"));print(d.get("message",""))' "$f" 2>/dev/null)
  ALERT=$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1],encoding="utf-8"));print(int(d.get("alert",0)))' "$f" 2>/dev/null)
  if [ -z "$MSG" ]; then
    mv -f "$f" "$DEAD/" 2>/dev/null; log "BAD $(basename "$f") 无法解析"; FAIL=$((FAIL+1)); continue
  fi
  if [ "$DRY" = "1" ]; then echo "[dry] $MSG"; SENT=$((SENT+1)); continue; fi
  if NOTIFY_NOQUEUE=1 bash "$W/tools/notify.sh" $([ "${ALERT:-0}" = "1" ] && echo --alert) "$MSG" >/dev/null 2>&1; then
    rm -f "$f"; SENT=$((SENT+1)); log "SENT $(basename "$f") ${MSG:0:40}"
  else
    mv -f "$f" "$DEAD/" 2>/dev/null; FAIL=$((FAIL+1)); log "FAIL->dead $(basename "$f") ${MSG:0:40}"
  fi
done

# dead/ 超过 50 个时告警一次（防止静默丢件）
DN=$(ls "$DEAD" 2>/dev/null | wc -l)
if [ "${DN:-0}" -ge 50 ] && [ "$DRY" = "0" ]; then
  NOTIFY_ALERT=1 NOTIFY_NOQUEUE=1 bash "$W/tools/notify.sh" --alert "通知补发积压：dead/$DN 条失败件，需人工看 $LOG" >/dev/null 2>&1 || true
fi
log "DONE sent=$SENT fail=$FAIL dead=$DN"
echo "notify-flush: sent=$SENT fail=$FAIL dead=$DN"
[ "$FAIL" -gt 0 ] && exit 3
exit 0
