#!/bin/bash
# model-pools-apply.sh v2 —— 本机模型分层下发（2026-10-24，双审必修项已合入）
# 用法: model-pools-apply.sh [--apply] [--include-l3] [--verify]
#       model-pools-apply.sh --rollback <备份文件>
set -uo pipefail
W=/home/j/.openclaw/workspace
LOG=$W/state/work/model-pools.log
LK=$W/state/work/model-pools.lock
mkdir -p "$(dirname "$LK")"
exec 9>"$LK"; flock -n 9 || { echo "SKIP 已有实例在跑"; exit 3; }
FB_CHAIN='{"primary":"deepseek/deepseek-flash","fallbacks":["deepseek/deepseek-v4-pro","zai/glm-5.3","ollama/qwen3:30b-a3b-instruct-2507-q4_K_M"]}'
L1='{"primary":"zai/glm-5.3-flash","fallbacks":["deepseek/deepseek-flash","zai/glm-5.3","deepseek/deepseek-v4-pro","ollama/qwen3:30b-a3b-instruct-2507-q4_K_M"]}'
L3='{"primary":"deepseek/deepseek-v4-pro","fallbacks":["deepseek/deepseek-flash","zai/glm-5.3","ollama/qwen3:30b-a3b-instruct-2507-q4_K_M"]}'
declare -A POOL=(
  [news]=L1 [cooking]=L1 [study]=L1 [security]=L1 [print]=L1 [sheet-music]=L1
)
declare -A POOL3=(
  [wealth]=L3 [tax]=L3 [health-self]=L3 [health-wife]=L3 [health-doudou]=L3 [mom-health]=L3
)
MODE=plan; INC_L3=0; RB=""
for a in "$@"; do case "$a" in --apply) MODE=apply;; --verify) MODE=verify;; --include-l3) INC_L3=1;; --rollback) MODE=rollback;; *) RB="$a";; esac; done
[ "$INC_L3" = "1" ] && for k in "${!POOL3[@]}"; do POOL[$k]="${POOL3[$k]}"; done
# 额度降级模式：pool-mode=fallback 时 L1 用 FB_CHAIN（避免 apply 重跑冲掉降级）
MODE_F=$W/state/model-econ/pool-mode.json
if [ -f "$MODE_F" ] && grep -q fallback "$MODE_F" 2>/dev/null; then L1="$FB_CHAIN"; fi
hit(){ case "$1" in L1) printf %s "$L1";; L3) printf %s "$L3";; esac; }

# ---- 探活：CLI 必须可用 ----
if ! openclaw config get agents.defaults.model >/dev/null 2>&1; then echo "❌ openclaw CLI 不可用，中止"; exit 4; fi

if [ "$MODE" = "rollback" ]; then
  [ -n "$RB" ] && [ -f "$RB" ] || { echo "用法: --rollback <备份文件>"; exit 2; }
  bad=0
  while IFS="|" read -r id val; do
    [ -n "$id" ] || continue
    if [ "$val" = "__ABSENT__" ]; then
      openclaw config unset "agents.entries.$id.model" >/dev/null 2>&1 || bad=$((bad+1))
    else
      openclaw config set "agents.entries.$id.model" --strict-json "$val" >/dev/null 2>&1 || bad=$((bad+1))
    fi
  done < "$RB"
  echo "回滚完成，失败 $bad 项"; [ "$bad" -eq 0 ] || exit 1; exit 0
fi

# ---- 采集现值（区分 缺失 / 读取失败）----
declare -A WANT CUR
for id in "${!POOL[@]}"; do
  j=$(hit "${POOL[$id]}")
  WANT[$id]="$j"
  out=$(openclaw config get "agents.entries.$id.model" 2>/dev/null); rc=$?
  if [ $rc -ne 0 ]; then echo "❌ 读取 $id 失败（CLI 异常），中止"; exit 4; fi
  if [ -z "$out" ] || [ "$out" = "null" ]; then CUR[$id]="__ABSENT__"; else CUR[$id]="$out"; fi
done

if [ "$MODE" = "verify" ]; then
  bad=0
  for id in "${!WANT[@]}"; do
    exp=$(printf %s "${WANT[$id]}" | tr -d " \n")
    got=$(printf %s "${CUR[$id]}" | tr -d " \n")
    if [ "$exp" = "$got" ]; then echo "✅ $id"; else echo "❌ $id 现:$got 期:$exp"; bad=$((bad+1)); fi
  done
  [ "$bad" -eq 0 ] && echo "VERIFY OK (${#WANT[@]} 项)" || { echo "VERIFY FAIL $bad 项"; exit 1; }; exit 0
fi

BK=$W/state/work/model-pools-rollback-$(date +%Y%m%d-%H%M%S).txt
: > "$BK"; for id in "${!CUR[@]}"; do echo "$id|${CUR[$id]}" >> "$BK"; done
echo "回滚基线: $BK"

if [ "$MODE" = "plan" ]; then
  for id in "${!WANT[@]}"; do echo "[演练] $id  ${CUR[$id]}  ->  ${WANT[$id]}" | cut -c1-160; done
  echo "演练完成，未写任何配置"; exit 0
fi

# ---- 原子下发：任一失败自动回滚 ----
bad=0
for id in "${!WANT[@]}"; do
  if openclaw config set "agents.entries.$id.model" --strict-json "${WANT[$id]}" >>"$LOG" 2>&1; then
    echo "✅ $id → ${POOL[$id]}"
  else echo "❌ $id 写入失败"; bad=$((bad+1)); fi
done
if [ "$bad" -ne 0 ]; then
  echo "⚠️ $bad 项失败，自动回滚到基线"; bash "$0" --rollback "$BK" || true; exit 1
fi
echo "全部下发成功（${#WANT[@]} 项）"; exit 0

