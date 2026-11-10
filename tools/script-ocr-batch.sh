#!/bin/bash
SRC=/mnt/e/openclaw-cloud-backup/剧本素材/inbound
OUT=/home/j/openclaw-workspaces/chinese/ocr-out
LOG=/home/j/.openclaw/workspace/state/work/script-ocr.log
mkdir -p "$OUT"
: > "$LOG"
n=0; ok=0; fail=0
while IFS= read -r f; do
  n=$((n+1))
  base=$(basename "$f")
  name=$(echo "$base" | sed -E "s/^input-//; s/---[0-9a-f-]{36}\.pdf$//; s/\.pdf$//")
  dst="$OUT/$name.txt"
  echo "[$(date '+%F %T')] ($n/44) $name" >> "$LOG"
  if timeout 300 /home/j/.openclaw/workspace/tools/ocr-file "$f" --out "$dst" >> "$LOG" 2>&1; then
    ok=$((ok+1))
  else
    fail=$((fail+1)); echo "  FAIL $base" >> "$LOG"
  fi
done < <(find "$SRC" -maxdepth 2 -name "*.pdf" | sort)
echo "[$(date '+%F %T')] DONE 总数=$n 成功=$ok 失败=$fail" >> "$LOG"
