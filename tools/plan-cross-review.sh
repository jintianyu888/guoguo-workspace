#!/usr/bin/env bash
# 方案逐条交叉验证：v4-pro + glm-5.3 各自独立判断
set -uo pipefail
W=/home/j/.openclaw/workspace
D="$W/state/tmp/xr"
OUT="$W/state/plan-cross-review.md"
: > "$OUT"
echo "# 方案逐条交叉验证  $(date '+%F %T')" >> "$OUT"

call() { # $1 model  $2 prompt file  $3 out file  $4 timeout
  local n=0
  while [ $n -lt 2 ]; do
    if timeout "$4" openclaw infer model run --agent main --gateway --model "$1" --prompt "$(cat "$2")" > "$3" 2>&1; then
      if [ -s "$3" ] && ! grep -q "took too long" "$3"; then return 0; fi
    fi
    n=$((n+1)); sleep 3
  done
  return 1
}

for id in P1 P2 P3 P4 P5 P6 P7 P8 P9; do
  T="$D/$id.txt"
  [ -f "$T" ] || continue
  printf '审查下面这一条方案，只回两行：\n判断: 可执行/需改/有安全风险\n理由: 一句话\n\n方案：%s\n' "$(cat "$T")" > "$D/p_$id.txt"
  if call deepseek/deepseek-v4-pro "$D/p_$id.txt" "$D/o_$id.ds" 180; then DS="$(tail -3 "$D/o_$id.ds" | tr '\n' ' ')"; else DS="【调用失败】"; fi
  if call zai/glm-5.3 "$D/p_$id.txt" "$D/o_$id.glm" 150; then GL="$(tail -3 "$D/o_$id.glm" | tr '\n' ' ')"; else GL="【调用失败】"; fi
  {
    echo ""
    echo "## $id"
    echo "- 方案：$(cat "$T")"
    echo "- v4-pro：$DS"
    echo "- glm-5.3：$GL"
  } >> "$OUT"
done
echo "" >> "$OUT"
echo "DONE $(date '+%F %T')" >> "$OUT"
echo CROSS_REVIEW_DONE
