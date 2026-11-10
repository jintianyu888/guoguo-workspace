#!/bin/bash
# asr-last.sh — 补转最近一条入站语音（任意管家可用）
# 用法: asr-last.sh [N]   默认最近 1 条；只看不走台账，直接出文字
set -uo pipefail
cd /home/j/.openclaw/workspace || exit 1
N=${1:-1}
find /home/j/.openclaw/media/inbound /home/j/.openclaw/workspace/media/inbound -maxdepth 2 -type f -name '*.ogg' -printf '%T@ %p\n' 2>/dev/null \
  | sort -rn | head -"$N" | awk '{print $2}' | while read -r f; do
    echo "== $(date -r "$f" +%H:%M:%S) $(stat -c%s "$f")B $(basename "$f")"
    timeout 240 ./tools/asr "$f" --language zh 2>/dev/null || echo "[转写失败]"
  done
