#!/bin/bash
# shutdown-alert.sh v2 — 关机前告警（2026-11-01 主公令）
# v2：预防层改走 tools/notify.sh --alert（进统一告警台账 alerts.jsonl）；
#     临终层保留直连 webhook（抢时间，绕开静默窗），但同样写台账，维护管家可查
set -uo pipefail
WS=/home/j/.openclaw/workspace
WH=/home/j/.config/feishu-alert-webhook
ALED=$WS/state/alerts/alerts.jsonl
LED=$WS/state/work/shutdown-alert.jsonl
LOGF=$WS/state/work/shutdown-alert.log
MARKD=$WS/state/work
KAP='^/bin/sh -c while true; do sleep 3600; done$'
SRC=shutdown-alert

log(){ printf '%s %s\n' "$(date -Iseconds)" "$*" >> "$LOGF"; }

ledger(){  # $1=text $2=delivered(0/1)  → 与 notify.sh 同 schema
  mkdir -p "$(dirname "$ALED")"
  (
    flock -x 8
    SRC="$SRC" TXT="$1" DEL="$2" python3 - <<'PYL'
import os,json,datetime
p="/home/j/.openclaw/workspace/state/alerts/alerts.jsonl"
rec={"ts":datetime.datetime.now().isoformat(timespec="seconds"),
     "source":os.environ.get("SRC","unknown"),
     "text":os.environ.get("TXT","")[:500],
     "delivered":os.environ.get("DEL","0")=="1"}
open(p,"a",encoding="utf-8").write(json.dumps(rec,ensure_ascii=False)+"\n")
PYL
  ) 8>>"$(dirname "$ALED")/.lock"
}

payload(){ python3 -c 'import json,sys;print(json.dumps({"msg_type":"text","content":{"text":sys.argv[1]}},ensure_ascii=False))' "$1"; }

direct(){  # $1=标题 $2=正文 → 0 成功
  local url p
  url=$(tr -d ' \r\n' < "$WH" 2>/dev/null)
  [ -n "$url" ] || return 1
  p=$(payload "【告警】$1
$2")
  curl -s --max-time 6 -H 'Content-Type: application/json' -d "$p" "$url" 2>/dev/null | grep -qE '"StatusCode"[[:space:]]*:[[:space:]]*0|"code"[[:space:]]*:[[:space:]]*0'
}

send(){  # $1=标题 $2=正文 $3=去重键 $4=notify|direct
  local key=$3 mode=$4 now last=0 rc=1
  now=$(date +%s)
  [ -f "$MARKD/.shutdown-alert.$key" ] && last=$(cat "$MARKD/.shutdown-alert.$key" 2>/dev/null || echo 0)
  if [ $((now-last)) -lt 120 ]; then return 0; fi
  echo "$now" > "$MARKD/.shutdown-alert.$key"
  if [ "$mode" = "direct" ]; then
    direct "$1" "$2"; rc=$?
    if [ $rc -ne 0 ]; then
      timeout 25 bash "$WS/tools/notify.sh" --alert "$1 | $2" >/dev/null 2>&1 && rc=0
    fi
    ledger "【告警】$1 | $2" "$([ $rc -eq 0 ] && echo 1 || echo 0)"
  else
    NOTIFY_SOURCE=$SRC NOTIFY_FROM=shutdown-alert NOTIFY_BELONG=maint timeout 40 bash "$WS/tools/notify.sh" --alert "$1 | $2" >/dev/null 2>&1
    rc=$?
  fi
  printf '{"ts":"%s","key":"%s","mode":"%s","title":"%s","sent":%s}\n' "$(date -Iseconds)" "$key" "$mode" "$1" "$([ $rc -eq 0 ] && echo true || echo false)" >> "$LED"
  log "ALERT key=$key mode=$mode sent=$rc title=$1"
  return 0
}

kap_alive(){ pgrep -fx "$KAP" >/dev/null 2>&1; }

check(){
  local s kap
  s=$(loginctl list-sessions --no-legend 2>/dev/null | wc -l)
  if kap_alive; then kap=在; else kap=不在; fi
  if [ "$kap" = "不在" ]; then
    send "保活进程不在了" "会话数=$s，随时会被 logind 关机。正在拉起 WSL-KeepAlive。" kap notify
    /mnt/c/Windows/System32/schtasks.exe /Run /TN WSL-KeepAlive >/dev/null 2>&1
    log "self-heal keepalive rc=$?"
  elif [ "$s" -le 1 ]; then
    send "只剩 1 个会话" "保活在，但会话数已降到 $s，再少一个就会自动关机。" sess notify
  fi
}

on_shutdown(){
  local trig=$1 tail15 sess kap gw
  tail15=$(journalctl -n 15 --no-pager -o short-iso 2>/dev/null | tail -15 | cut -c1-160)
  sess=$(loginctl list-sessions --no-legend 2>/dev/null | awk '{print $1"("$3")"}' | paste -sd' ' -)
  if kap_alive; then kap=在; else kap=不在; fi
  gw=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:18789/health 2>/dev/null)
  send "WSL 整机即将关机" "触发行：$trig
会话：$sess
保活：$kap ｜ 网关 /health：$gw

最后 15 行日志：
$tail15" shutdown direct
  log "SHUTDOWN DETECTED: $trig"
}

if [ "${1:-}" = "--test" ]; then
  send "关机告警自检" "TEST：模拟关机信号，验证台账与投递链路。" test direct
  send "保活自检" "TEST：验证经 notify.sh 进统一台账。" test2 notify
  echo 'test alerts sent'; exit 0
fi

run_watch(){
  local line rc
  while :; do
    IFS= read -r -t 60 line; rc=$?
    if [ $rc -eq 0 ]; then
      case "$line" in
        *'will power off now'*|*'System is powering down'*|*'Powering off.'*|*'PrepareForShutdown'*) on_shutdown "$line" ;;
      esac
    elif [ $rc -gt 128 ]; then
      check
    else
      return 0
    fi
  done
}

log 'started v2'
check
while :; do
  run_watch < <(journalctl -f -n 0 -o short-iso 2>/dev/null)
  sleep 5
  check
done
