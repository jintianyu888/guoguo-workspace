#!/bin/bash
# 9070XT 本地大模型(ollama) 通断探活 —— 只读，零 token
# 用法: llm-local-check.sh   输出一行状态；状态变化时提示
HOST=${LLM_LOCAL_HOST:-192.168.1.107}
PORT=${LLM_LOCAL_PORT:-11434}
STATE=/home/j/.openclaw/workspace/state/llm-local-state.txt
V=$(timeout 6 curl -s -m 5 "http://$HOST:$PORT/api/version" 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin).get('version',''))" 2>/dev/null)
if [ -n "$V" ]; then
  NOW="UP v$V"
else
  NOW="DOWN"
fi
PREV=$(cat "$STATE" 2>/dev/null || echo "unknown")
echo "$NOW" > "$STATE"
if [ "$NOW" = "$PREV" ]; then
  echo "[llm-local] $NOW ($HOST:$PORT) · 无变化"
else
  if [ "$NOW" = "DOWN" ]; then
    echo "⚠️ [llm-local] 9070XT 本地模型 不通 ($HOST:$PORT) · 状态 $PREV → DOWN"
  else
    echo "✅ [llm-local] 9070XT 本地模型 已恢复 ($HOST:$PORT) · $NOW"
  fi
fi
