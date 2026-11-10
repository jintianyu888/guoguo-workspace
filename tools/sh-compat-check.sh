#!/bin/bash
# sh-compat-check.sh —— 防复发：凡是「用 sh 调用」的脚本，必须 sh 语法兼容
# 教训（2026-10-01）：backup-retain.sh 用了 bash 专属语法却被备份流程用 sh 调用
# → 每次备份都报 "Syntax error: redirection unexpected"，报错好几天没人发现
W=/home/j/.openclaw/workspace
cd "$W" || exit 0
bad=0
# 1) 找出所有 "sh <path>" 形式的调用，取其目标脚本
targets=$(grep -rhoE '(^|[^a-zA-Z])sh +(/home/j/\.openclaw/workspace/)?tools/[A-Za-z0-9_.-]+\.sh' tools/ *.sh 2>/dev/null \
  | sed -E 's|.*(tools/[A-Za-z0-9_.-]+\.sh)|\1|' | sort -u)
n=0
for t in $targets; do
  [ -f "$t" ] || continue
  n=$((n+1))
  if ! sh -n "$t" 2>/dev/null; then
    echo "❌ 被 sh 调用但 sh 语法不兼容: $t"
    echo "   → $(sh -n "$t" 2>&1 | head -n1)"
    bad=$((bad+1))
  fi
done
echo "🔎 sh 兼容检查: 共查 $n 个被 sh 调用的脚本，异常 $bad 个"
[ "$bad" -gt 0 ] && exit 1 || exit 0
