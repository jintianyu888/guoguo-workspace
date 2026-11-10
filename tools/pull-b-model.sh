#!/bin/bash
OUT=/home/j/.openclaw/workspace/state/work/pull-$1.log
curl -sN --max-time 5400 -X POST http://127.0.0.1:11434/api/pull \
  -d "{\"model\":\"$1\",\"stream\":true}" > "$OUT" 2>&1
echo "PULL_RC=$? model=$1" >> "$OUT"