#!/usr/bin/env bash
# panel-watchdog.sh — 8899 果果助手面板健康探测与自愈（零 token）
# 2026-11-12 建立：guoguo.service 是 Type=simple + Restart=always，
#   "进程活着但 HTTP 卡死"这类假活它抓不到（11-11 曾挂 23 小时），故外挂本探针。
# 行为：探测 -> 失败隔 15s 复测 -> 仍失败才重启 guoguo.service -> 记日志 -> 推一条告警
# 限制：只碰 guoguo.service（用户级），绝不触碰 gateway。
set -u
URL="http://127.0.0.1:8899/"
UNIT="guoguo.service"
LOG=/home/j/.openclaw/workspace/state/work/panel-watchdog.log
LOCK=/tmp/oc-panel-watch.lock
mkdir -p "$(dirname "$LOG")"

exec 9>"$LOCK" || exit 0
flock -n 9 || exit 0

ts() { date '+%F %T'; }
probe() { local c; c=$(curl -s -o /dev/null -w '%{http_code}' -m 10 "$URL" 2>/dev/null); [ -z "$c" ] && c=000; echo "$c"; }

code=$(probe)
if [ "$code" = "200" ]; then
  echo "$(ts) OK 200" >> "$LOG"
  exit 0
fi

echo "$(ts) PROBE1=$code retest-in-15s" >> "$LOG"
sleep 15
code2=$(probe)
if [ "$code2" = "200" ]; then
  echo "$(ts) RECOVERED 200 (no restart)" >> "$LOG"
  exit 0
fi

echo "$(ts) PROBE2=$code2 restart $UNIT" >> "$LOG"
systemctl --user restart "$UNIT" >> "$LOG" 2>&1
sleep 5
code3=$(probe)
echo "$(ts) AFTER_RESTART=$code3" >> "$LOG"

if [ "$code3" = "200" ]; then
  bash /home/j/.openclaw/workspace/tools/notify.sh "面板自愈：果果助手 8899 探测连续失败（$code/$code2），已自动重启 guoguo.service，现恢复正常。" >> "$LOG" 2>&1
  exit 0
else
  bash /home/j/.openclaw/workspace/tools/notify.sh "面板异常：果果助手 8899 探测失败（$code/$code2），自动重启后仍为 $code3，需人工看一眼。" >> "$LOG" 2>&1
  exit 2
fi
