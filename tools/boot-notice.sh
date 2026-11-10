#!/usr/bin/env bash
# boot-notice.sh v2 (2026-10-31) — WSL 开机报平安，每 boot 仅一次
# v2 修正：boot_id 读不到不再用 unknown 键；flock 超时即退出；网关不就绪走独立告警通道
set -uo pipefail
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1
W=/home/j/.openclaw/workspace
STATE=$W/state/work
LOG=$STATE/boot-notice.log
mkdir -p "$STATE"

BOOT_ID=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)
if [ -z "$BOOT_ID" ]; then
  echo "$(date '+%F %T') 无法读取 boot_id，跳过去重保护并直接发送" >> "$LOG"
  MARK=""
else
  MARK=$STATE/.boot-notice-$BOOT_ID
fi

exec 9>/tmp/boot-notice.lock
if ! flock -w 30 9; then
  echo "$(date '+%F %T') 获取锁超时，退出（避免双发）" >> "$LOG"
  exit 0
fi

if [ -n "$MARK" ] && [ -f "$MARK" ]; then
  echo "skip: boot $BOOT_ID 已报过" >> "$LOG"
  exit 0
fi

ok=0
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 3 http://127.0.0.1:18789/ 2>/dev/null)
  [ "$code" = "200" ] && { ok=1; break; }
  sleep 2
done

ts=$(date '+%F %T')
if [ $DRY -eq 1 ]; then echo "DRY: would notify (gateway ok=$ok)"; exit 0; fi
# 2026-11-03 修正（双审）：notify.sh 默认投递失败也 exit 0，造成回执"假绿"。
# 改用 NOTIFY_STRICT=1 拿真实 rc；失败再试 1 次（间隔 60s，覆盖开机后渠道连通延迟），仍失败升级告警并留痕。
deliver(){
  local flag="$1" body="$2" rc=1
  NOTIFY_STRICT=1 timeout 120 bash "$W/tools/notify.sh" $flag "$body" >>"$LOG" 2>&1
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "$ts 首次投递失败(rc=$rc)，60s 后重试" >> "$LOG"
    sleep 60
    NOTIFY_STRICT=1 timeout 120 bash "$W/tools/notify.sh" $flag "$body （重发）" >>"$LOG" 2>&1
    rc=$?
  fi
  return $rc
}
if [ $ok -eq 1 ]; then
  msg="【开机报平安】$ts WSL 已启动，网关就绪（HTTP 200）"
  if deliver "--to-owner" "$msg"; then rc=0; else
    rc=1
    mkdir -p "$STATE"; echo "$ts 开机回执两次投递失败" >> "$STATE/BOOT-NOTICE-UNDELIVERED"
    timeout 60 bash "$W/tools/notify.sh" --alert "【告警】开机回执投递失败（已重试 1 次）：$ts 网关已就绪但消息未送达，请检查渠道" >>"$LOG" 2>&1 || true
  fi
else
  msg="【告警】开机报平安：$ts WSL 已启动，但网关 180 秒内未就绪，请查看"
  if deliver "--alert" "$msg"; then rc=0; else rc=1; fi
fi

echo "$ts rc=$rc $msg" >> "$LOG"
[ $rc -eq 0 ] && [ -n "$MARK" ] && touch "$MARK"
exit 0
