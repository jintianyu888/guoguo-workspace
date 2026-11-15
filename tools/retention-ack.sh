#!/bin/bash
# retention-ack.sh — 人工回执：确认已看过本月保留策略预演
set -u
W=/home/j/.openclaw/workspace
M=$W/state/work/retention-receipt-needed
[ -f "$M" ] || { echo "无需回执"; exit 0; }
d=$(cat "$M")
echo "$(date '+%F %T') ack $d" >> $W/state/work/retention-receipts.log
rm -f "$M"
echo "已回执：$d 的保留策略预演"