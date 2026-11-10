#!/bin/bash
# 补跑第二家评审（用精简提示，规避网关 120s 超时）
cd /home/j/.openclaw/workspace || exit 0
OC=/home/j/.npm-global/bin/openclaw
P=$(cat state/tmp/rev-plan-short.txt)
DONE=0
run_one() {
  m="$1"; shift
  n=$(echo "$m" | tr '/' '_')
  timeout 400 "$OC" infer model run --agent main --gateway --model "$m" "$@" --prompt "$P" > "state/tmp/rev-retry-$n.txt" 2>&1
  B=$(wc -c < "state/tmp/rev-retry-$n.txt")
  echo "$(date '+%F %T') $m $B bytes" >> state/work/rev-retry.log
  [ "$B" -gt 400 ] && DONE=$((DONE+1))
}
run_one kimi-coding/kimi-k3.1-pro --thinking on
run_one zai/glm-5.3
if [ "$DONE" -gt 0 ]; then
  MSG=$(head -c 900 state/tmp/rev-retry-kimi*.txt 2>/dev/null; head -c 900 state/tmp/rev-retry-zai*.txt 2>/dev/null)
  timeout 25 bash tools/notify.sh --alert "待办机制·第二家评审补跑完成（$DONE 家有效）：$MSG" >/dev/null 2>&1
else
  timeout 25 bash tools/notify.sh --alert "告警：待办机制·第二家评审仍失败，需人工介入" >/dev/null 2>&1
fi
