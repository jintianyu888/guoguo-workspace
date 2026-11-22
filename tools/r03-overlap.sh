#!/usr/bin/env bash
# r03-overlap.sh —— R03 调度重叠守门（2026-11-22 改判定口径，零 token）
# 口径：① 当前真实重叠数不得高于基线 ② 基线只降不升（降了自动写回）。
# 先 sync 再统计——schedule.db 不会自己更新，不同步就是拿旧数据判定（今天踩过）。
set -uo pipefail
WS=/home/j/.openclaw/workspace
BASE_F=$WS/state/work/overlap-baseline.json
cd "$WS" || exit 1
python3 tools/schedule-plan.py sync >/dev/null 2>&1
OUT=$(python3 tools/schedule-plan.py overlaps 2>&1)
N=$(echo "$OUT" | grep -oP '合计 \K\d+')
[ -n "$N" ] || { echo "❌ R03 取不到重叠数"; exit 1; }
if [ -f "$BASE_F" ]; then
  B=$(python3 -c "import json;print(json.load(open('$BASE_F'))['baseline'])")
else
  B=$N
  printf '{"baseline": %s, "set_at": "%s"}\n' "$N" "$(date '+%F %T')" > "$BASE_F"
fi
if [ "$N" -le "$B" ]; then
  if [ "$N" -lt "$B" ]; then
    printf '{"baseline": %s, "set_at": "%s"}\n' "$N" "$(date '+%F %T')" > "$BASE_F"
    echo "✅ R03 重叠 $N 处（低于基线 $B，基线已下调）"
  else
    echo "✅ R03 重叠 $N 处（等于基线 $B）"
  fi
  exit 0
fi
echo "❌ R03 重叠升到 $N 处（基线 $B）→ 逐条看："
echo "$OUT" | sed -n '2,12p'
exit 1
