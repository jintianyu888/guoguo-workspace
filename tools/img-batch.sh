#!/usr/bin/env bash
# img-batch.sh v1.1 (2026-11-21) —— 批量出图（顺序执行，遇 429 自动退避重试）
# 说明：智谱免费档并发=1，3 路并发会 429（实测），所以默认串行；付费档可试 --parallel 2
# 用法：bash tools/img-batch.sh "提示词" [张数=3] [--model cogview-4] [--size 1440x960] [--parallel N]
set -uo pipefail
WS=/home/j/.openclaw/workspace
PROMPT="$1"; N="${2:-3}"; shift 2 2>/dev/null || shift 1
MODEL=cogview-4; SIZE=1440x960; PAR=1
while [ $# -gt 0 ]; do case "$1" in --model) MODEL="$2"; shift 2;; --size) SIZE="$2"; shift 2;; --parallel) PAR="$2"; shift 2;; *) shift;; esac; done
STAMP=$(date +%Y%m%d-%H%M%S)
gen() {
  local i="$1" out="$2" try=0
  while [ $try -lt 3 ]; do
    if python3 "$WS/tools/img-gen.py" "$PROMPT" --model "$MODEL" --size "$SIZE" --out "$out" >"/tmp/imgb-$i.log" 2>&1; then
      echo "OK $out"; return 0
    fi
    if grep -q "429" "/tmp/imgb-$i.log"; then try=$((try+1)); sleep $((try*3)); else break; fi
  done
  echo "FAIL $out"; tail -2 "/tmp/imgb-$i.log"; return 1
}
ok=0; running=0
for i in $(seq 1 "$N"); do
  gen "$i" "$WS/data/images/batch-$STAMP-$i.png" &
  running=$((running+1))
  if [ "$running" -ge "$PAR" ]; then wait -n; running=$((running-1)); fi
  [ "$PAR" -eq 1 ] && wait
done
wait
for i in $(seq 1 "$N"); do [ -s "$WS/data/images/batch-$STAMP-$i.png" ] && ok=$((ok+1)); done
echo "完成 $ok/$N 张｜model=$MODEL size=$SIZE par=$PAR"
[ "$ok" -eq "$N" ]