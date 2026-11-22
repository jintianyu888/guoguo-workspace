#!/usr/bin/env bash
# r33-secretary.sh —— R33 秘书机制已同步到全体管家且入口可用（零 token）
set -uo pipefail
WS=/home/j/.openclaw/workspace
fail=0
grep -q "三·五、秘书机制" "$WS/docs/管家通用守则.md" || { echo "❌ 通用守则缺秘书条款"; fail=1; }
OUT=$(bash "$WS/tools/agent-common-sync.sh" --check 2>&1 | tail -1)
echo "$OUT" | grep -q "旧版 0" || fail=1
echo "$OUT" | grep -q "未注入 0" || fail=1
python3 "$WS/tools/advice-ask.py" --help >/dev/null 2>&1 || { echo "❌ advice-ask.py 不可用"; fail=1; }
if [ "$fail" -eq 0 ]; then
  echo "✅ R33 秘书机制已同步：$OUT"
fi
exit $fail
