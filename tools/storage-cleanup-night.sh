#!/bin/bash
# storage-cleanup-night.sh —— 02:15 一次性：b2→b3→b1 顺序清理
set -uo pipefail
W=/home/j/.openclaw/workspace
LOG=$W/state/work/storage-cleanup-night.log
echo "=== NIGHT START $(date "+%F %T") ===" >> $LOG
for b in b2 b3 b1; do
  echo "--- $b ---" >> $LOG
  timeout 3600 bash $W/tools/storage-cleanup.sh $b --apply >> $LOG 2>&1
  echo "$b rc=$?" >> $LOG
done
echo "=== NIGHT END $(date "+%F %T") ===" >> $LOG
ok=$(grep -c "已移入回收站" $LOG 2>/dev/null || echo 0)
bash $W/tools/notify.sh "🧹 存储清理完成：$ok 项已移入回收站，详见 state/work/storage-cleanup-night.log" >/dev/null 2>&1 || true

