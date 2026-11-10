#!/bin/bash
OUT=/home/j/openclaw-workspaces/chinese/ocr-out
LOG=/home/j/.openclaw/workspace/state/work/script-ocr.log
i=0
while IFS= read -r f; do
  i=$((i+1))
  dst="$OUT/花禾A-副本$i.txt"
  echo "[$(date '+%F %T')] 补跑 花禾A #$i" >> "$LOG"
  timeout 300 /home/j/.openclaw/workspace/tools/ocr-file "$f" --out "$dst" >> "$LOG" 2>&1
done < <(find /mnt/e/openclaw-cloud-backup/剧本素材/inbound -maxdepth 2 -name "input-花禾A---*.pdf" | sort)
echo "[$(date '+%F %T')] 补跑完成" >> "$LOG"
