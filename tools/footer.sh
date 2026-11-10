#!/bin/bash
# 页脚实时数据 v2 · 每项独立超时 + 并行 + 缓存兜底（永不阻塞）
cd /home/j/.openclaw/workspace || exit 1
TMP=$(mktemp -d)
# 并行取三项，各自硬超时
( timeout 10 sh tools/ds-balance.sh 2>/dev/null | tail -1 > "$TMP/bal" ) &
( timeout 10 sh tools/peak-status.sh 2>/dev/null | sed -n '2p' > "$TMP/peak" ) &
( timeout 10 sh tools/host-peak-report.sh 2>/dev/null | grep -E 'CPU 负载峰值|内存峰值' | tr '\n' ' ' > "$TMP/host" ) &
wait
bal=$(cat "$TMP/bal" 2>/dev/null | tr -d '\n')
peak=$(cat "$TMP/peak" 2>/dev/null | tr -d '\n')
host=$(cat "$TMP/host" 2>/dev/null | tr -d '\n')
rm -rf "$TMP"
# 余额兜底：读缓存文件（若有）
if [ -z "$bal" ]; then
  for f in /tmp/ds-balance.cache /home/j/.openclaw/workspace/state/ds-balance.cache; do
    [ -f "$f" ] && bal="$(tail -1 "$f" 2>/dev/null)（缓存）" && break
  done
fi
echo "· 余额: ${bal:-取不到}"
echo "· 时段: ${peak:-取不到}"
echo "· 主机: ${host:-取不到}"
echo "· 此刻: $(date '+%Y-%m-%d %H:%M:%S')"
