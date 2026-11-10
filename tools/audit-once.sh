#!/usr/bin/env bash
# audit-once.sh —— 单路审查（可控测时/测费），2026-10-24
# 用法: bash tools/audit-once.sh <model> [材料文件]
set -uo pipefail
W=/home/j/.openclaw/workspace
MODEL="${1:-deepseek/deepseek-v4-pro}"
mkdir -p $W/state/tmp
MAT="${2:-$W/state/tmp/audit-mat.txt}"
ROLE='你是独立代码审查员。材料含【脚本清单】与【证据包（文件:行号:原文）】。严格规则：每条结论必须以「文件:行号」开头并引用该行原文；引用不到行号的问题一律不要写；禁止凭文件名猜测。审查项：1) 语法/逻辑错误 2) 同一文件被多脚本写 3) 危险操作（rm、无备份删除、明文密钥）4) 定时任务风险 5) 可优化。格式：- [严重|中|低] 文件:行 类别 | 描述（含原文引用） | 建议；首行：结论: 正常 或 结论: 问题N项。'
{
  printf '%s\n材料：\n' "$ROLE"
  cat "$MAT"
} > $W/state/tmp/audit-prompt.txt
T0=$(date +%s)
timeout 420 openclaw infer model run --agent main --gateway --model "$MODEL" --prompt "$(cat $W/state/tmp/audit-prompt.txt)" > $W/state/tmp/audit-once.out 2>&1
RC=$?
T1=$(date +%s)
echo "MODEL=$MODEL RC=$RC SECONDS=$((T1-T0)) BYTES=$(wc -c < $W/state/tmp/audit-once.out)" | tee $W/state/tmp/audit-once.meta
