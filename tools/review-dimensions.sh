#!/usr/bin/env bash
# review-dimensions.sh — 重大变更强制三问（30天反噬 / 服务目标 / 沉没成本）
# 定位：L2 双审的前置自检。不装 cron、不自动触发；任何重大变更（改脚本/配置/账本/cron/备份策略/对外动作）提交前跑一次。
# 用法：
#   tools/review-dimensions.sh --change "一句话改动描述或提案文件路径" [--out 文件] [--no-write]
#   tools/review-dimensions.sh --change x --call    # 走便宜档模型自动填答（需 REVIEW_MODEL_CMD）
# 约定：
#   - 默认 --out state/review/dim-$(date +%Y%m%d)-<seq>.md
#   - --call 不硬编码厂商；REVIEW_MODEL_CMD 由调用方给（如 'openclaw model call --model cheap'），没有就只出模板
#   - 三问必须逐条落字，"说不清" 也是结论；任何一问答不出 → 该变更不得进双审
set -euo pipefail
WS="${WS:-/home/j/.openclaw/workspace}"
CHANGE=""; OUT=""; WRITE=1; CALL=0
while [ $# -gt 0 ]; do
  case "$1" in
    --change) CHANGE="${2:-}"; shift 2;;
    --out)    OUT="${2:-}"; shift 2;;
    --no-write) WRITE=0; shift;;
    --call)   CALL=1; shift;;
    -h|--help) sed -n '2,12p' "$0"; exit 0;;
    *) echo "未知参数: $1" >&2; exit 2;;
  esac
done
[ -n "$CHANGE" ] || { echo "用法: $0 --change \"改动描述\" [--out 文件] [--no-write] [--call]" >&2; exit 2; }
[ -f "$CHANGE" ] && CHANGE="$(head -c 2000 "$CHANGE")"

TS="$(date '+%Y-%m-%d %H:%M')"
if [ -z "$OUT" ]; then
  mkdir -p "$WS/state/review"
  OUT="$WS/state/review/dim-$(date +%Y%m%d).md"
  n=1; while [ -e "$OUT" ] && [ "$n" -lt 99 ]; do n=$((n+1)); OUT="$WS/state/review/dim-$(date +%Y%m%d)-$n.md"; done
fi

PROMPT="你是评审员。只回答三问，逐条给结论与可验证信号，不要客套。
变更：$CHANGE
问 1 · 30天反噬：30 天后这个改动最可能反噬什么？列出具体失败模式 + 出现时最早可观测的信号。
问 2 · 服务目标：它服务哪个目标？不做会怎样？有没有更小成本的替代方案？
问 3 · 沉没成本：为它已投入什么？如果今天从零开始，还会这么做吗？"

{
  echo "# 重大变更三问 · $TS"
  echo
  echo "变更：$CHANGE"
  echo
  if [ "$CALL" = 1 ] && [ -n "${REVIEW_MODEL_CMD:-}" ]; then
    echo "## 自动填答（$REVIEW_MODEL_CMD）"
    echo
    printf '%s' "$PROMPT" | bash -c "$REVIEW_MODEL_CMD" 2>/dev/null || {
      echo "> 模型调用失败，回落到人工模板。"; echo; }
  else
    [ "$CALL" = 1 ] && { echo "> 未设 REVIEW_MODEL_CMD，未联网，回落到人工模板。"; echo; }
  fi
  cat <<'TPL'
## 问 1 · 30 天反噬
- 失败模式：
- 最早信号（可观测、可告警）：
- 触发后的回滚动作：

## 问 2 · 服务目标
- 服务的目标：
- 不做的后果：
- 更小成本的替代：

## 问 3 · 沉没成本
- 已投入：
- 今天从零还会做吗：
- 若否，停在哪一步：

## 结论
- [ ] 三问均已落字（任何一问空白 → 不进双审）
- 评审人/时间：
TPL
} > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
[ "$WRITE" = 1 ] && echo "已写入 $OUT" || echo "（--no-write 未落盘）"
cat "$OUT"
