#!/bin/sh
# gpu-guard.sh —— GPU 低负载门控：查利用率/显存；忙了就等（可设超时）
# 用法: tools/gpu-guard.sh [--max-util 70] [--min-free-mb 1500] [--wait 300]
MAXU=70; MINFREE=1500; WAIT=300
while [ $# -gt 0 ]; do
  case "$1" in
    --max-util) MAXU=$2; shift 2;;
    --min-free-mb) MINFREE=$2; shift 2;;
    --wait) WAIT=$2; shift 2;;
    *) shift;;
  esac
done
NVS="/usr/lib/wsl/lib/nvidia-smi"; [ -x "$NVS" ] || NVS=$(command -v nvidia-smi 2>/dev/null)
[ -n "$NVS" ] || { echo "NO_GPU_TOOL"; exit 0; }
i=0
while [ $i -lt $WAIT ]; do
  U=$($NVS --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | tr -d ' ' | cut -d. -f1)
  F=$($NVS --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | tr -d ' ' | cut -d. -f1)
  [ -z "$U" ] && { echo "NO_GPU_TOOL"; exit 0; }
  if [ "$U" -le "$MAXU" ] && [ "$F" -ge "$MINFREE" ]; then echo "OK util=${U}% free=${F}MB"; exit 0; fi
  sleep 5; i=$((i+5))
done
echo "BUSY util=${U}% free=${F}MB"; exit 1