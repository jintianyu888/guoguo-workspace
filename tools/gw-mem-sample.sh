#!/bin/bash
# 网关内存采样（2026-11-07，#228）：每 5 分钟记 RSS/PSS/anon，供画曲线定位日增
set -uo pipefail
WS=/home/j/.openclaw/workspace
OUT=$WS/state/mem/rss.jsonl
mkdir -p "$WS/state/mem"
P=$(pgrep -f 'node .*openclaw/dist/index.js gat' | head -1)
[ -z "${P:-}" ] && { echo "$(date +%s) 0 0 0 0 none" >> "$OUT"; exit 0; }
RSS=$(awk '/^VmRSS:/{print $2}' /proc/$P/status 2>/dev/null)
PS=$(awk '/^Pss:/{print $2}' /proc/$P/smaps_rollup 2>/dev/null)
ANON=$(awk '/^Anonymous:/{print $2}' /proc/$P/smaps_rollup 2>/dev/null)
UP=$(ps -o etimes= -p $P 2>/dev/null | tr -d ' ')
printf '{"ts":%s,"pid":%s,"rss_kb":%s,"pss_kb":%s,"anon_kb":%s,"uptime_s":%s}\n' \
  "$(date +%s)" "${P:-0}" "${RSS:-0}" "${PS:-0}" "${ANON:-0}" "${UP:-0}" >> "$OUT"
# 只留 30 天
[ $(wc -l < "$OUT") -gt 8640 ] && tail -n 8000 "$OUT" > "$OUT.tmp" && mv "$OUT.tmp" "$OUT"
exit 0
