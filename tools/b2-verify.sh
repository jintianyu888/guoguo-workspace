#!/bin/bash
set -uo pipefail
cd /home/j/.openclaw/workspace
mkdir -p state/tmp
IDX=state/tmp/b2-idx.txt
OUT=state/work/b2-verified.txt; : > "$OUT"
ls -l /mnt/h/openclaw-backups/*.tar.gz /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | awk '{print $5"|"$9}' > "$IDX"
ok=0; miss=0
while IFS= read -r f; do
  b=$(basename "$f"); s=$(stat -c %s "$f" 2>/dev/null)
  m=$(awk -F"|" -v s="$s" -v b="$b" '$1==s && index($2,b)>0 {print $2; exit}' "$IDX")
  if [ -n "$m" ]; then echo "OK|$b|$s|$m" >> "$OUT"; ok=$((ok+1)); else echo "NO_REPLICA|$b|$s" >> "$OUT"; miss=$((miss+1)); fi
done < <(find /mnt/e/openclaw-backups/_trash -type f -name "*.tar.gz" 2>/dev/null)
echo "SUMMARY ok=$ok miss=$miss" >> "$OUT"

