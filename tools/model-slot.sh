#!/bin/bash
# model-slot.sh —— 按时段切换主力模型
# 2026-10-19 主公令：工作日高峰档（09-12，DeepSeek 全价）走 GLM 省真金白银；
# 半价档（午间12-14、18点后夜间、周末节假日全天）走 deepseek-flash——半价便宜，且不烧 GLM 积分
# 2026-10-23 主公令：下午档（14-18）改走 Kimi 月卡日常档 kimi-for-coding（订阅内零边际），GLM 留守上午高峰
# 用法: model-slot.sh peak|afternoon|offpeak
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/work/model-slot.log
mkdir -p "$W/state/work"
GLM='{"primary":"zai/glm-5.3-flash","fallbacks":["zai/glm-5.3","kimi-coding/kimi-for-coding","deepseek/deepseek-flash","deepseek/deepseek-v4-pro","ollama/qwen3:30b-a3b-instruct-2507-q4_K_M"]}'
KIMI='{"primary":"kimi-coding/kimi-for-coding","fallbacks":["zai/glm-5.3-flash","zai/glm-5.3","deepseek/deepseek-flash","deepseek/deepseek-v4-pro","ollama/qwen3:30b-a3b-instruct-2507-q4_K_M"]}'
DS='{"primary":"deepseek/deepseek-flash","fallbacks":["zai/glm-5.3-flash","zai/glm-5.3","kimi-coding/kimi-for-coding","deepseek/deepseek-v4-pro","ollama/qwen3:30b-a3b-instruct-2507-q4_K_M"]}'
case "${1:-}" in
  peak)           JSON="$GLM" ;;   # 上午高峰全价档：GLM 主力
  afternoon)      JSON="$GLM" ;;  # 下午档：GLM 主力（避开编码卡 ToS），Kimi 仅在 fallback 链
  offpeak)        JSON="$DS" ;;    # 半价档：DeepSeek 主力
  *) echo "用法: $0 peak|afternoon|offpeak" >&2; exit 2;;
esac
if openclaw config set agents.defaults.model --strict-json "$JSON" >>"$LOG" 2>&1; then
  echo "== $(date '+%F %T') 切到 $1 ==" >> "$LOG"
else
  echo "== $(date '+%F %T') 切换失败 ($1) ==" >> "$LOG"; exit 1
fi
