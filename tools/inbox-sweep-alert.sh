#!/bin/bash
# 主理人收件箱积压告警（配合 cron 每小时跑）
cd /home/j/.openclaw/workspace || exit 0
OUT=$(python3 tools/inbox-sweep.py --max-age 45 2>&1); RC=$?
if [ $RC -ne 0 ]; then
  timeout 60 bash tools/notify.sh --alert "【收件箱积压】$(echo "$OUT" | tail -2 | tr '\n' ' ')" >/dev/null 2>&1
fi
echo "$OUT"
exit 0
