#!/bin/bash
# butler-audit-guard.sh — 13:35 校验五大管家今日是否真做了自审（零 token）
set -uo pipefail
cd /home/j/.openclaw/workspace
timeout 180 /usr/bin/python3 tools/butler-review-harvest.py >/dev/null 2>&1
OUT=$(timeout 150 /usr/bin/python3 tools/butler-daily.py --check 2>&1)
if echo "$OUT" | grep -q "ALL_OK"; then
  echo "$OUT" | tail -2
  exit 0
fi
MISS=$(echo "$OUT" | grep "MISSING:" | sed 's/MISSING://')
echo "missing: $MISS"
bash tools/notify.sh "🕵️ 五大管家自审缺失（13:35 校验）：${MISS}
判据：工作区 state/self-review/$(date +%F).md 不存在。已记录 state/butler/today.json，明日 12:25 起重试；连续两天缺失升级处理。" >/dev/null 2>&1
exit 1
