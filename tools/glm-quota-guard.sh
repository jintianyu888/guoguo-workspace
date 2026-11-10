#!/bin/bash
# glm-quota-guard.sh v0.1 — 检测 GLM 撞墙(429/1305)，写降级状态供调度层使用
set -u
WS=/home/j/.openclaw/workspace
STATE=$WS/state/model-econ/glm-quota-state.json
mkdir -p "$WS/state/model-econ"
NOW=$(date +%s)
HITS=$(journalctl --user -u openclaw-gateway --since "-6h" --no-pager 2>/dev/null | grep -iE 'zai|glm' | grep -icE '429|1305|rate.?limit|quota' || true)
HITS=${HITS:-0}
TRIPPED=false
UNTIL=0
if [ "$HITS" -ge 3 ]; then
  TRIPPED=true
  UNTIL=$((NOW + 5*3600))
fi
if [ -f "$STATE" ]; then
  PREV=$(python3 -c "import json;print(json.load(open('$STATE')).get('tripped',False))" 2>/dev/null || echo False)
else
  PREV=False
fi
cat > "$STATE.tmp" <<EOF
{"tripped": $TRIPPED, "until": $UNTIL, "hits_6h": $HITS, "updated": "$(date -Iseconds)"}
EOF
mv "$STATE.tmp" "$STATE"
if [ "$TRIPPED" != "$PREV" ]; then
  if [ "$TRIPPED" = "true" ]; then
    bash "$WS/tools/notify.sh" "🔴 GLM 撞墙：6h 内限流命中 $HITS 次，已标记降级 5 小时（规划层将暂时绕开 GLM）" 2>/dev/null || true
  else
    bash "$WS/tools/notify.sh" "🟢 GLM 限流解除：6h 内命中 $HITS 次，恢复正常调度" 2>/dev/null || true
  fi
fi
echo "hits=$HITS tripped=$TRIPPED until=$UNTIL"
