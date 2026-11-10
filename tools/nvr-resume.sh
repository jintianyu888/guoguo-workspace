#!/usr/bin/env bash
# nvr-resume.sh — 06:10 静默窗后 NVR 扫描续跑入口（P3 2026-10-26）
# 日期来源优先级：state/work/nvr-resume-date（03:50 checkpoint 写入）→ 昨日
# 用独立脚本包一层，避免 cron 里写 $() 被创建时求值（实测会被固化）。
set -u
W=/home/j/.openclaw/workspace
RD=$W/state/work/nvr-resume-date
D=$(cat "$RD" 2>/dev/null | tr -d '[:space:]')
[ -z "$D" ] && D=$(date -d yesterday +%F)
echo "[$(date '+%F %T')] nvr-resume start date=$D" >> $W/state/work/nvr-face-scan.log
# 2026-10-27 修（维护日清·双审通过 glm-5.3 + kimi-k3.1-pro）：
# 下游 rc=3 = 上一轮仍在跑（锁冲突），属正常跳过，不再让 cron 记 error；
# 但加锁龄护栏：锁龄 >12h 视为僵死持锁，仍按真错误透传（防无限 SKIP 全绿）。
bash "$W/tools/nvr-scan-daily.sh" "$D" &
NVR_PID=$!
echo "[$(date '+%F %T')] nvr-resume run pid=$NVR_PID date=$D"
cleanup(){
  if kill -0 "$NVR_PID" 2>/dev/null; then
    kill -TERM "$NVR_PID" 2>/dev/null
    sleep 5
    kill -0 "$NVR_PID" 2>/dev/null && kill -KILL "$NVR_PID" 2>/dev/null
  fi
}
trap cleanup EXIT INT TERM
next_hb=$(( $(date +%s) + 600 ))
while kill -0 "$NVR_PID" 2>/dev/null; do
  sleep 10
  NOW=$(date +%s)
  if [ "$NOW" -ge "$next_hb" ] && kill -0 "$NVR_PID" 2>/dev/null; then
    echo "[$(date '+%F %T')] nvr-resume heartbeat pid=$NVR_PID 扫描进行中"
    next_hb=$(( NOW + 600 ))
  fi
done
wait "$NVR_PID"; rc=$?
trap - EXIT INT TERM
if [ "$rc" -eq 3 ]; then
  LK=$W/state/work/nvr-scan-daily.lock
  NOW=$(date +%s)
  MT=$(stat -c %Y "$LK" 2>/dev/null || echo "$NOW")
  AGE=$(( NOW - MT ))
  if [ "$AGE" -gt 43200 ]; then
    echo "[$(date '+%F %T')] nvr-resume WARN 锁龄 ${AGE}s >12h，疑似僵死持锁，按错误上报" >> $W/state/work/nvr-face-scan.log
    exit 3
  fi
  echo "[$(date '+%F %T')] nvr-resume SKIP 上一轮仍在跑（锁龄 ${AGE}s），本轮不重复启动" >> $W/state/work/nvr-face-scan.log
  exit 0
fi
exit "$rc"
