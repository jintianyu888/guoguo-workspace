#!/bin/bash
set -uo pipefail
L=/home/j/.openclaw/workspace/state/work/bench.log
exec >> "$L" 2>&1
echo "=== bench start $(date +%H:%M:%S) ==="
t0=$(date +%s)
tar -cf /dev/null /home/j/.openclaw
t1=$(date +%s)
echo "tar遍历+读(无压缩无写): $((t1-t0)) 秒  34GB → $(( 34*1024/(t1-t0) )) MB/s"
for lvl in 6 1; do
  s=$(date +%s)
  gzip -$lvl -c /home/j/.openclaw/lcm.db > /dev/null
  e=$(date +%s)
  echo "gzip -$lvl lcm.db(306MB): $((e-s)) 秒 → $(( 306/(e-s) )) MB/s"
done
echo "=== bench done $(date +%H:%M:%S) ==="
