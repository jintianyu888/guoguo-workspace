#!/bin/bash
# deadman.sh —— 独立看护"看护者"（2026-11-26 立，解决 11-26 十小时无人发现）
# 每 5 分钟：① 网关 health 连续 2 次异常 → 告警 ② 15 分钟快照超过 45 分钟没成功 → 告警
#            ③ 看门狗 timer 不在 active → 告警。告警 1 小时冷却，一处写日志。
set -uo pipefail
export PATH=/usr/bin:/bin:/home/j/.npm-global/bin
W=/home/j/.openclaw/workspace
LOG="$W/state/work/deadman.log"
CNT="$W/state/work/.deadman-fail"
COOL="$W/state/work/.deadman-alert-ts"
say(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }
alert(){
  NOW=$(date +%s); LAST=$(cat "$COOL" 2>/dev/null || echo 0)
  if [ $((NOW - LAST)) -ge 3600 ]; then
    echo "$NOW" > "$COOL"
    timeout 60 bash "$W/tools/notify.sh" --alert "$1" >/dev/null 2>&1 || true
    say "ALERT $1"
  fi
}

H=$(timeout 8 curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/health 2>/dev/null)
if [ "$H" != "200" ]; then
  N=$(cat "$CNT" 2>/dev/null || echo 0); N=$((N+1)); echo "$N" > "$CNT"
  say "health=$H 连续异常 $N 次"
  if [ "$N" -ge 2 ]; then alert "【DEADMAN】网关 health=$H 连续 $N 次（5 分钟/次），看门狗可能已失效"; fi
else
  echo 0 > "$CNT"
fi

OKF=/home/j/.openclaw/state/backups/.last-ok
if [ -f "$OKF" ]; then
  LASTOK=$(cat "$OKF" 2>/dev/null || echo 0)
  NOW=$(date +%s)
  AGE=$(( (NOW - LASTOK) / 60 ))
  if [ "$AGE" -gt 45 ]; then alert "【DEADMAN】state 15 分钟快照已 $AGE 分钟未成功（RPO 目标 15 分钟已破）"; fi
else
  alert "【DEADMAN】找不到 state 快照心跳文件 .last-ok，备份可能从未成功"
fi

if ! systemctl --user is-active --quiet oc-gateway-watchdog.timer; then
  alert "【DEADMAN】看门狗 timer 未在运行，网关无人看守"
fi
if ! systemctl --user is-active --quiet oc-state-backup.timer; then
  alert "【DEADMAN】state 备份 timer 未在运行"
fi
say "health=$H 快照心跳=$(cat "$OKF" 2>/dev/null | head -c 12)"
tail -n 400 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
