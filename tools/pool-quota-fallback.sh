#!/bin/bash
# pool-quota-fallback.sh —— L1 订阅池的额度闭环（2026-10-23，双审 A4 必修）
# 读 state/model-econ/glm-quota-state.json，周额度>=85% 或 5h窗口>=95% → L1 降级到 flash
# 周额度<=70% 且 窗口<=80% → 恢复 GLM。带迟滞，避免来回抖。
# 用法: pool-quota-fallback.sh [--dry-run] [--force]
set -uo pipefail
W=/home/j/.openclaw/workspace
ST=$W/state/model-econ/glm-quota-state.json
MODE=$W/state/model-econ/pool-mode.json
LOG=$W/state/work/pool-quota.log
LK=$W/state/work/pool-quota.lock
mkdir -p "$(dirname "$LK")" "$(dirname "$LOG")"
exec 9>"$LK"; flock -n 9 || { echo "SKIP 并发"; exit 3; }
L1='{"primary":"zai/glm-5.3-flash","fallbacks":["deepseek/deepseek-flash","zai/glm-5.3","deepseek/deepseek-v4-pro","ollama/qwen3:30b-a3b-instruct-2507-q4_K_M"]}'
FB='{"primary":"deepseek/deepseek-flash","fallbacks":["deepseek/deepseek-v4-pro","zai/glm-5.3","ollama/qwen3:30b-a3b-instruct-2507-q4_K_M"]}'
IDS="news cooking study security print sheet-music"
DRY=0; FORCE=0
for a in "$@"; do case "$a" in --dry-run) DRY=1;; --force) FORCE=1;; esac; done
[ -f "$ST" ] || { echo "无配额状态文件 $ST，跳过"; exit 0; }
read -r WK WIN < <(python3 -c "import json;d=json.load(open('$ST'));print(int(d.get('panel_weekly_pct') or d.get('weekly_pct') or 0), int(d.get('panel_window_pct') or d.get('window_pct') or 0))")
cur="glm"
[ -f "$MODE" ] && cur=$(python3 -c "import json;print(json.load(open('$MODE')).get('mode','glm'))" 2>/dev/null || echo glm)
target="$cur"
if [ "$FORCE" = "0" ]; then
  if [ "$cur" = "glm" ] && { [ "$WK" -ge 85 ] || [ "$WIN" -ge 95 ]; }; then target="fallback"; fi
  if [ "$cur" = "fallback" ] && [ "$WK" -le 70 ] && [ "$WIN" -le 80 ]; then target="glm"; fi
else
  target="${FORCE_MODE:-fallback}"
fi
echo "[$(date "+%F %T")] 周=${WK}% 窗口=${WIN}% 现=$cur 目标=$target" | tee -a "$LOG"
if [ "$target" = "$cur" ]; then exit 0; fi
if [ "$target" = "fallback" ]; then J="$FB"; else J="$L1"; fi
bad=0
for id in $IDS; do
  if [ "$DRY" = "1" ]; then echo "[演练] $id -> $target"; continue; fi
  openclaw config set "agents.entries.$id.model" --strict-json "$J" >>"$LOG" 2>&1 || bad=$((bad+1))
done
if [ "$DRY" = "0" ] && [ "$bad" -eq 0 ]; then
  printf '{"mode":"%s","weekly_pct":%s,"window_pct":%s,"ts":"%s"}\n' "$target" "$WK" "$WIN" "$(date -Is)" > "$MODE.tmp" && mv "$MODE.tmp" "$MODE"
  echo "[$(date "+%F %T")] 已切到 $target（6 个 L1 agent）" | tee -a "$LOG"
fi
[ "$bad" -eq 0 ] || { echo "❌ $bad 项失败" | tee -a "$LOG"; exit 1; }

