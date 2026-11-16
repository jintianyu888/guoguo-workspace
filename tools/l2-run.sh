#!/bin/bash
# l2-run.sh —— 管家 L2 动作统一入口（冻结检查 + 自动入账）
# 用法: bash tools/l2-run.sh <butler> "<命令>"
set -uo pipefail
BUTLER="${1:?用法: l2-run.sh <butler> \"命令\"}"
shift
CMD="${*:?缺命令}"
ROOT=/home/j/.openclaw/workspace
FREEZE="$ROOT/state/work/butlers-frozen"
if [ -e "$FREEZE" ]; then
  echo "REFUSED: L2 已冻结（存在 $FREEZE）" >&2
  exit 91
fi
START=$(date -Iseconds)
OUT=$(bash -c "$CMD" 2>&1); RC=$?
echo "$OUT"
python3 "$ROOT/tools/exec-ledger.py" add "L2[$BUTLER] $CMD" --category deploy \
  --done $([ $RC -eq 0 ] && echo ok || echo fail) \
  --reused "l2-run 包装" --optimized "无" \
  --evidence "rc=$RC $(echo "$OUT" | head -c 200 | tr '\n' ' ')" \
  --rollback "见命令本身" >/dev/null 2>&1 || true
exit $RC
