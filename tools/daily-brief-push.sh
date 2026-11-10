#!/bin/bash
# daily-brief-push.sh [morning|evening] —— 生成并推送果果简报
set -uo pipefail
cd /home/j/.openclaw/workspace || exit 1
SLOT="${1:-morning}"
# 先跑验证器：能机器验证的条目按真实状态自动关闭
python3 tools/ledger-verify.py --apply >/dev/null 2>&1 || true
python3 tools/tasks-db.py export >/dev/null 2>&1 || true
OUT=$(python3 tools/daily-brief.py "$SLOT" 2>&1) || { OUT="简报生成失败：$OUT"; }
printf '%s\n' "$OUT"
timeout 60 bash tools/notify.sh "$OUT" >/dev/null 2>&1
