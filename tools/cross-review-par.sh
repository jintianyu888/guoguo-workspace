#!/bin/bash
# cross-review-par.sh v1.0 —— 并发评审：发 N+1 家，先回 N 家有效即定案
# 依据 docs/并发评审提速方案-v0.1-20261101.md v1.0 定稿（双审 GO-WITH-FIXES）
# 用法: cross-review-par.sh --prompt-file F --task NAME [--n 2|3]
set -uo pipefail
export PATH="/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
WS=/home/j/.openclaw/workspace
PROMPT=""; TASK="review"; N=2
while [ $# -gt 0 ]; do
  case "$1" in
    --prompt-file) PROMPT="$2"; shift 2;;
    --task) TASK="$2"; shift 2;;
    --n) N="$2"; shift 2;;
    *) shift;;
  esac
done
[ -f "$PROMPT" ] || { echo "ERR 缺 --prompt-file"; exit 2; }
case "$N" in 2|3) ;; *) echo "ERR --n 只能 2/3"; exit 2;; esac
WANT=$((N+1))

# 厂商池（旗舰档；flash/preview/turbo 不进）
POOL=("zai|zai/glm-5.3" "kimi|kimi-coding/kimi-k3.1-pro" "minimax|minimax/MiniMax-M3" "qianwen|qianwen-token-plan/qwen3.8-max")

# 随机洗牌取 WANT 家
mapfile -t SEL < <(printf "%s\n" "${POOL[@]}" | shuf | head -n "$WANT")

OUT=$(date +%Y%m%d-%H%M%S)
DIR="$WS/state/work/cross-review/$OUT"
mkdir -p "$DIR"
echo "== 并发评审: $TASK (发 $WANT 家，取先回 $N 家) =="
printf "%s\n" "${SEL[@]}" | while IFS="|" read -r v m; do echo "  - $v: $m"; done

TMP=$(mktemp -d)
for entry in "${SEL[@]}"; do
  v="${entry%%|*}"; m="${entry##*|}"
  ( start=$(date +%s)
    THK=""
    case "$v" in
      kimi) THK="--thinking low";;
      minimax) THK="";;
      *) THK="";;
    esac
    timeout 420 openclaw infer model run --model "$m" --gateway $THK --prompt "$(cat "$PROMPT")" > "$TMP/$v.txt" 2>&1
    rc=$?; end=$(date +%s)
    b=$(wc -c < "$TMP/$v.txt" 2>/dev/null || echo 0)
    ok=0
    if [ "$rc" -eq 0 ] && [ "$b" -ge 200 ] && ! grep -qiE "Couldn.t connect|ECONNREFUSED|not authenticated|rate limit|无法读取|cannot read" "$TMP/$v.txt"; then ok=1; fi
    echo "$rc $b $ok $((end-start))" > "$TMP/$v.meta"
    python3 /home/j/.openclaw/workspace/tools/review-ledger.py --model "$m" --vendor "$v" --bytes "$b" --duration "$((end-start))" --rc "$rc" --valid "$ok" --task "$TASK" >/dev/null 2>&1
    cp "$TMP/$v.txt" "$DIR/$v.txt" 2>/dev/null
  ) &
done

# 轮询收集，够 N 家即停
GOT=0; WAITED=0
while [ "$WAITED" -lt 450 ]; do
  GOT=0
  for entry in "${SEL[@]}"; do
    v="${entry%%|*}"
    if [ -f "$TMP/$v.meta" ]; then
      read -r rc b ok el < "$TMP/$v.meta"
      [ "$ok" = "1" ] && GOT=$((GOT+1))
    fi
  done
  [ "$GOT" -ge "$N" ] && break
  sleep 3; WAITED=$((WAITED+3))
done

echo "--- 收集结果（有效 $GOT 家，用时 ${WAITED}s）---"
for entry in "${SEL[@]}"; do
  v="${entry%%|*}"
  if [ -f "$TMP/$v.meta" ]; then
    read -r rc b ok el < "$TMP/$v.meta"
    echo "$v: rc=$rc ${b}B 有效=$ok 耗时=${el}s"
  else
    echo "$v: 未返回（超时）"
  fi
done
echo "输出: $DIR"
if [ "$GOT" -lt "$N" ]; then echo "[结论] 不足 $N 家有效，本次不算审过"; exit 1; fi
echo "[结论] 达到 $N 家有效，可定案（注意：其余家仍在跑，若有 REJECT 后到需按延时否决处理）"