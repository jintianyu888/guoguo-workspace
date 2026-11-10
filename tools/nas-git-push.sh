#!/bin/bash
# L2：把各工作区推到群晖 ws-*.git（每 4h 镜像，自动提交未保存改动）
set -uo pipefail
OK=0; SK=0; FA=0
# 镜像范围由配置派生（agents.entries[*].workspace），不再用 workspace* 通配，避免孤儿目录被反复提交
WS_LIST=$(python3 - <<'PY'
import json, os
c = json.load(open('/home/j/.openclaw/openclaw.json'))
seen = set()
for k, v in (c.get('agents') or {}).get('entries', {}).items():
    w = ((v or {}).get('workspace') or '').strip()
    if w and os.path.isdir(w) and w not in seen:
        seen.add(w); print(w)
PY
)
for d in $WS_LIST; do
  [ -d "$d/.git" ] || { SK=$((SK+1)); continue; }
  u=$(git -C "$d" remote get-url origin 2>/dev/null || true)
  [ -n "$u" ] || { SK=$((SK+1)); continue; }
  git -C "$d" add -A >/dev/null 2>&1
  git -C "$d" -c user.name=openclaw -c user.email=openclaw@local commit -q -m "auto mirror $(date +%Y-%m-%dT%H:%M)" >/dev/null 2>&1
  if timeout 120 git -C "$d" push -q origin HEAD >/dev/null 2>&1; then OK=$((OK+1)); else FA=$((FA+1)); echo "  ⚠️ 推送失败: $(basename "$d")"; fi
done
echo "🔼 L2 工作区推送 · $(date +%Y-%m-%dT%H:%M)"
echo "· 成功 $OK · 跳过 $SK · 失败 $FA"
