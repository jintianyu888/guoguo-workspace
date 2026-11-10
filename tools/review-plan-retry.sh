#!/usr/bin/env bash
# review-plan-retry.sh — 双机方案双审补跑（2026-10-27 前两次因网关繁忙超时）
set -uo pipefail
export PATH="/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
OCL=/home/j/.npm-global/bin/openclaw
[ -x "$OCL" ] || { echo "ERR: openclaw CLI not found" >&2; exit 127; }
cd /home/j/.openclaw/workspace
OUT=state/work/review-b3
mkdir -p "$OUT"
P=state/work/review-b2-prompt.txt
sleep 90
run() {
  local name="$1" model="$2"
  timeout 420 "$OCL" infer model run --agent main --gateway --model "$model" --thinking off --prompt "$(cat "$P")" > "$OUT/$name.md" 2>&1
  local rc=$?
  echo "$name rc=$rc bytes=$(wc -c < "$OUT/$name.md" 2>/dev/null)" >> "$OUT/status.txt"
}
: > "$OUT/status.txt"
run v4pro deepseek/deepseek-v4-pro
run minimax minimax/MiniMax-M3.1-Flash-Preview
run kimi kimi-coding/kimi-k3.1-pro
{
  echo "【双审补跑结果】$(date '+%m-%d %H:%M')"
  echo "$(cat "$OUT/status.txt" | tr '\n' ' ')"
  for f in v4pro minimax kimi; do
    echo "--- $f ---"
    head -c 420 "$OUT/$f.md" 2>/dev/null
    echo
  done
} > "$OUT/summary.txt"
timeout 40 bash tools/notify.sh "双机模型方案·双审补跑结果（详见 state/work/review-b3/summary.txt）
$(cat "$OUT/status.txt" | tr '\n' ' ')
$(head -c 600 "$OUT/summary.txt" | tail -c 400)" >/dev/null 2>&1
