#!/bin/bash
# cc.sh —— Claude Code 指向 DeepSeek 兼容端点的安全封装（2026-11-15 试点）
# 用法:
#   bash tools/cc.sh "分析xxx"                 # 只读（默认，禁止写文件/执行命令）
#   bash tools/cc.sh --write --dir /tmp/p "改xxx"  # 允许读写（限指定目录）
# 说明: DeepSeek 端点在「无轮次上限 + 多文件」时会挂死，默认 --max-turns 8，超限自动停。
set -uo pipefail
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_AUTH_TOKEN="${DEEPSEEK_APP_KEY:?缺少 DEEPSEEK_APP_KEY}"
export ANTHROPIC_API_KEY="$ANTHROPIC_AUTH_TOKEN"
export ANTHROPIC_MODEL="${CC_MODEL:-deepseek-chat}"
export ANTHROPIC_SMALL_FAST_MODEL="$ANTHROPIC_MODEL"

WRITE=0; DIR="$HOME/.openclaw/workspace"; TURNS=8
while [ $# -gt 0 ]; do
  case "$1" in
    --write) WRITE=1; shift;;
    --dir) DIR="$2"; shift 2;;
    --turns) TURNS="$2"; shift 2;;
    --model) export ANTHROPIC_MODEL="$2"; export ANTHROPIC_SMALL_FAST_MODEL="$2"; shift 2;;
    *) break;;
  esac
done
PROMPT="${1:?用法: cc.sh [--write] [--dir D] [--turns N] \"提示词\"}"
cd "$DIR" || exit 2
ARGS=(-p "$PROMPT" --model "$ANTHROPIC_MODEL" --max-turns "$TURNS")
[ "$WRITE" = 1 ] && ARGS+=(--dangerously-skip-permissions) || ARGS+=(--permission-mode plan)
exec claude "${ARGS[@]}"
