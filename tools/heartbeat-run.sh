#!/bin/bash
# heartbeat-run.sh —— 前台跑长任务，同时每分钟吐一次心跳，避免"无输出超时"被误杀
# 用法: heartbeat-run.sh <命令...>
set -uo pipefail
[ $# -ge 1 ] || { echo "用法: heartbeat-run.sh <命令...>"; exit 2; }
"$@" &
PID=$!
n=0
while kill -0 "$PID" 2>/dev/null; do
  sleep 10
  n=$((n+1))
  # 2026-10-26 A4 修：心跳从每 1 分钟改每 5 分钟。原来 30 分钟任务会吐 30 行心跳，
  #  把 cron 的 2000 字诊断摘要挤满，真正的"结束/退出码"被截掉 → 督察判"产出指纹不符"。
  if [ $((n % 30)) -eq 0 ] && kill -0 "$PID" 2>/dev/null; then
    echo "[heartbeat] 运行中 $((n/6)) 分钟（pid $PID）"
  fi
done
wait "$PID"
RC=$?
echo "[heartbeat] 结束，退出码 $RC，用时约 $((n/6)) 分钟"
exit "$RC"
