#!/bin/bash
# advice-retry-glm.sh —— 智谱额度重置后重问风险评审并推送（一次性）
set -uo pipefail
cd /home/j/.openclaw/workspace
python3 tools/advice-ask.py --plan state/advice/plan-20261126-gateway.md --advisor glm \
  --goal "11.10 留守期的稳定护栏与新版本启用/回退判据（风险与漏项视角）" > /tmp/advice-glm-retry.log 2>&1
LATEST=$(ls -t state/advice/*-glm.md 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then
  timeout 60 bash tools/notify.sh --alert "【秘书·智谱】重问失败，见 /tmp/advice-glm-retry.log" >/dev/null 2>&1 || true
  exit 1
fi
BODY=$(sed -n '1,40p' "$LATEST")
timeout 90 bash tools/notify.sh "【秘书·智谱｜风险评审】
$BODY" >/dev/null 2>&1 || true
echo "done $LATEST"
