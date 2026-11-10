#!/bin/bash
# 修复降级插件依赖（2026-10-15 事故善后）——网关托管执行
[ -n "${BASH_VERSION:-}" ] || { echo "需用 bash 运行: bash $0" >&2; exit 1; }
LOG=/home/j/.openclaw/workspace/state/plugin-deps-repair.log
OUT=/home/j/.openclaw/workspace/state/plugin-deps-repair.md
REG=https://registry.npmmirror.com
exec > >(tee -a "$LOG") 2>&1
echo "=== START $(date '+%F %T') ==="
for p in memory-lancedb tavily diffs lossless-claw duckduckgo openshell tokenjuice; do
  D="/home/j/.openclaw/extensions/$p"
  [ -d "$D" ] || { echo "SKIP $p (no dir)"; continue; }
  echo "---- $p ----"
  ( cd "$D" && npm install --omit=dev --no-audit --no-fund --registry="$REG" >/home/j/.openclaw/workspace/state/tmp/npm-$p.log 2>&1; echo "rc=$?" )
  tail -3 /home/j/.openclaw/workspace/state/tmp/npm-$p.log
done
echo "=== reload plugins ==="
for p in memory-lancedb tavily diffs lossless-claw duckduckgo openshell tokenjuice feishu; do
  echo "-- reload $p"; openclaw plugins reload "$p" 2>&1 | tail -2
done
echo "=== triage ==="
openclaw triage 2>&1 | grep -E '^\[plugins\]' | head -20
echo "=== doctor warnings ==="
openclaw doctor 2>&1 | grep -iE 'failed|missing|warning' | head -20
{
  echo "# 插件依赖修复 $(date '+%F %T')"
  echo
  echo "## 各插件装依赖结果"
  for p in memory-lancedb tavily diffs lossless-claw duckduckgo openshell tokenjuice; do
    echo "- $p: nm=$(ls /home/j/.openclaw/extensions/$p/node_modules 2>/dev/null | wc -l) 个包"
  done
  echo
  echo "## triage 剩余告警"
  openclaw triage 2>&1 | grep -E '^\[plugins\]' | head -10
} > "$OUT"
echo "=== DONE $(date '+%F %T') ==="
