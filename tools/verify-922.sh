#!/bin/bash
# 922 验收：备份哈希清单改每日跑，单盘上限放宽到 30 分钟
set -u
out=$(openclaw cron list 2>/dev/null)
grep -q '备份哈希清单(每日)' <<<"$out" || exit 1
grep -q 'CAP=${CAP_MINUTES:-30}' /home/j/.openclaw/workspace/tools/manifest-nightly.sh || exit 1
exit 0
