#!/bin/bash
# backup-janitor.sh v1.0 —— 失败件/半成品自动清理
set -u
export PATH=/home/j/.npm-global/bin:/usr/bin:/bin
W=/home/j/.openclaw/workspace
LED="python3 $W/tools/backup-ledger.py"
LOG=$W/state/work/backup-janitor.log
say() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }
$LED scan >/dev/null 2>&1
out=$($LED janitor --hours 6 --apply 2>&1)
echo "$out" | while IFS= read -r l; do say "$l"; done
for f in /home/j/backup-stage/*.tar.gz; do
  [ -f "$f" ] || continue
  m=$(( ( $(date +%s) - $(stat -c %Y "$f") ) / 60 ))
  if [ "$m" -gt 360 ]; then rm -f "$f" && say "清暂存 $(basename "$f") 龄 $((m/60))h"; fi
done
$LED scan >/dev/null 2>&1
say OK 清理完成