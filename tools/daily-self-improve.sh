#!/bin/bash
# daily-self-improve.sh — 每天跑一次量化 + 候选改进，有高优先级才推送
set -u
WS=/home/j/.openclaw/workspace
OUT=$WS/state/improve/today.txt
mkdir -p "$WS/state/improve"
/usr/bin/python3 "$WS/tools/self-improve.py" > "$OUT" 2>&1
# 只有出现高优先级退化项才推飞书（[80]/[88]/[90]），避免打扰
if grep -qE '^\[(80|88|90)\]' "$OUT"; then
  bash "$WS/tools/notify.sh" "每日自我提升：发现高优先级退化项
$(grep -E '^\[(80|88|90)\]' "$OUT" | head -2)" 2>/dev/null || true
fi
exit 0
