#!/usr/bin/env bash
# r35-peer-review.sh v1.1 — 互审必须真交换（2026-11-25 起生效，11-24 为改造日）
set -uo pipefail
W=/home/j/.openclaw/workspace
D=$(date +%F); H=$(date +%H)
if [[ "$D" < "2026-11-25" ]]; then echo "SKIP 改造首日（契约 2026-11-25 生效）"; exit 0; fi
if [ "$H" -lt 14 ]; then echo "SKIP 未到 14:00"; exit 0; fi
miss=""
for a in backup maint model work; do
  [ -s "$W/state/butler/review/$D/$a.md" ] || miss="$miss $a"
done
if [ -n "$miss" ]; then
  echo "RED 今日互审交换文件缺失:$miss（用 tools/review-exchange.sh submit 补）"
  exit 1
fi
echo "GREEN 互审交换完整（backup/maint/model/work）"
