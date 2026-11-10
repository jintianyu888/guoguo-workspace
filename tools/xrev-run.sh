#!/bin/bash
# xrev-run.sh MODEL ITEM... —— 对每条方案调一个模型独立评审（硬超时，避免卡死）
set -u
W=/home/j/.openclaw/workspace
D=$W/state/tmp/xrev
MODEL=$1; shift
TAG=$(echo "$MODEL" | tr '/:' '__')
for k in "$@"; do
  out=$D/$k.$TAG.txt
  if [ -s "$out" ]; then echo "SKIP $k"; continue; fi
  rm -f "$out" "$out.err"
  timeout -k 5 50 openclaw infer model run --agent main --gateway --model "$MODEL" --prompt "$(cat $D/$k.txt)" > "$out" 2>"$out.err"
  rc=$?
  sz=$(wc -c < "$out" 2>/dev/null || echo 0)
  echo "[$k] rc=$rc size=${sz}B"
done