#!/bin/sh
# gpu-run.sh —— A 机 GPU 任务串行门（8G 显存只允许 1 个 GPU 任务）
# 用法: tools/gpu-run.sh <命令...>   超时: GPU_LOCK_WAIT 秒（默认 1800）
set -u
WS=/home/j/.openclaw/workspace
LOCK="$WS/state/locks/gpu.lock"
mkdir -p "$WS/state/locks"
exec 9>"$LOCK"
if ! flock -w "${GPU_LOCK_WAIT:-1800}" 9; then
  echo "GPU_LOCK_TIMEOUT: 等锁超过 ${GPU_LOCK_WAIT:-1800}s，放弃本次" >&2
  exit 75
fi
# 显存/利用率门控（拿不到就继续，不阻塞任务本身）
[ -x "$WS/tools/gpu-guard.sh" ] && sh "$WS/tools/gpu-guard.sh" --max-util 70 --min-free-mb 1200 --wait 180 >/dev/null 2>&1 || true
exec "$@"
