#!/bin/bash
# cross-review.sh v1.1 — 真随机交叉评审（2026-10-26 主公令）
set -uo pipefail
# PATH 兜底（2026-10-30）：systemd/cron 环境 PATH 精简，导致 openclaw 找不到 → 评审空跑
export PATH="/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin:/home/j/.openclaw/tmp/agent-cli:/home/j/.local/bin:/home/j/.npm-global/bin:/usr/bin:/bin:/usr/local/bin:/home/j/bin:/home/j/.nix-profile/bin:/snap/bin"
WS=/home/j/.openclaw/workspace
STATE=$WS/state/work/cross-review-pick.json
LEDGER=$WS/docs/交叉验证台账.md
PROMPT=""; TASK="任务"; N=2; DRY=0; DRYPICK=0
while [ $# -gt 0 ]; do
  case "$1" in
    --prompt-file) PROMPT="$2"; shift 2;;
    --task) TASK="$2"; shift 2;;
    --n) N="$2"; shift 2;;
    --dry-pick) DRYPICK=1; shift;;
    --dry-run) DRY=1; shift;;
    *) echo "未知参数: $1"; exit 2;;
  esac
done
case "$N" in 2|3|4) ;; *) echo "ERR --n 只能是 2/3/4"; exit 2;; esac

POOLF="/home/j/.openclaw/workspace/state/model-econ/review-pool.json"
if [ -f "$POOLF" ]; then
  mapfile -t VENDORS < <(python3 /home/j/.openclaw/workspace/tools/review-pool-print.py "$POOLF")
else
  # 2026-11-02：删掉旧硬编码兜底（里面含已封禁的 deepseek-v4-pro / MiniMax Preview），
  # 池文件缺失时宁可拒跑，也不静默用过期池。
  echo "ERR 评审池文件缺失: $POOLF —— 拒绝评审（请先修池）"
  exit 3
fi
# 守门人：池自洽 / 文档漂移 / 台账合规（2026-11-02 加）
if ! python3 "$WS/tools/review-pool-guard.py" --quiet; then
  echo "ERR 评审池体检未过，拒绝评审。修好再跑：python3 tools/review-pool-guard.py"
  exit 4
fi
pick() { printf '%s\n' "${VENDORS[@]}" | sort -R | head -n "$N"; }

LAST=""
if [ -f "$STATE" ]; then
  LAST=$(python3 -c "import json;print(','.join(sorted(json.load(open('$STATE'))['vendors'])))" 2>/dev/null)
fi
SEL=""
for try in 1 2 3 4 5; do
  SEL=$(pick)
  CUR=$(printf '%s\n' "$SEL" | cut -d'|' -f1 | sort | paste -sd, -)
  [ "$CUR" != "$LAST" ] && break
done
VNAMES=$(printf '%s\n' "$SEL" | cut -d'|' -f1 | paste -sd+ -)

if [ $DRYPICK = 1 ]; then
  echo "本次抽中（$N 家）：$VNAMES"
  printf '%s\n' "$SEL" | while IFS='|' read -r v m t; do echo "  - $v : $m $t"; done
  [ -n "$LAST" ] && echo "上一组：$LAST"
  exit 0
fi
[ -f "$PROMPT" ] || { echo "ERR 缺少 --prompt-file"; exit 2; }

python3 - "$STATE" "$SEL" <<'PY'
import json,sys,time
st,sel=sys.argv[1],sys.argv[2]
v=[l.split('|')[0] for l in sel.strip().split('\n') if l]
json.dump({'vendors':v,'at':time.strftime('%Y-%m-%dT%H:%M:%S')},open(st,'w'),ensure_ascii=False)
PY

KEEP=$WS/state/work/cross-review/$(date +%Y%m%d-%H%M%S)
mkdir -p "$KEEP"
TMPD=$(mktemp -d)
echo "== 交叉评审: $TASK =="
echo "本次评审: $VNAMES （随机 $N 家不同厂商）"
OK=0; FAILED=""
# 2026-10-29 修：优先直连模型（不经网关）。网关路径在长提示下会被队列饱和打成 178 字节失败。
run_one(){
  local M="$1" THK="$2" OUT="$3"
  if [ -n "$THK" ]; then
    timeout 300 openclaw infer model run --model "$M" --thinking "$THK" --prompt "$(cat "$PROMPT")" > "$OUT" 2>&1
  else
    timeout 300 openclaw infer model run --model "$M" --prompt "$(cat "$PROMPT")" > "$OUT" 2>&1
  fi
  RC=$?; B=$(wc -c < "$OUT" 2>/dev/null || echo 0)
  if [ "$RC" -ne 0 ] || [ "$B" -lt 30 ]; then
    echo "  (直连未成，退回网关路径重试)"
    if [ -n "$THK" ]; then
      timeout 300 openclaw infer model run --model "$M" --gateway --thinking "$THK" --prompt "$(cat "$PROMPT")" > "$OUT" 2>&1
    else
      timeout 300 openclaw infer model run --model "$M" --gateway --prompt "$(cat "$PROMPT")" > "$OUT" 2>&1
    fi
    RC=$?; B=$(wc -c < "$OUT" 2>/dev/null || echo 0)
  fi
}
while IFS='|' read -r V M THK; do
  [ -z "$V" ] && continue
  echo "--- [$V] $M 运行中..."
  if [ $DRY = 1 ]; then echo "  (dry-run)"; continue; fi
  run_one "$M" "$THK" "$TMPD/$V.txt"
  RC=$?; B=$(wc -c < "$TMPD/$V.txt" 2>/dev/null || echo 0)
  # 2026-11-07 修：原来按 ≥200 字节判成功，短而正确的回答被判 FAIL（实际 4 次 0/2 的假失败来源之一）
  BODY=$(sed '1,/^outputs: /d' "$TMPD/$V.txt" 2>/dev/null | tr -d '[:space:]')
  BL=${#BODY}
  if [ $RC -eq 0 ] && [ "$BL" -ge 1 ] && ! grep -qiE "Couldn.t connect to OpenClaw|openclaw gateway status|ECONNREFUSED|not authenticated|rate limit|quota|invalid_api_key" "$TMPD/$V.txt"; then echo "  OK ($B 字节, 正文 $BL 字)"; OK=$((OK+1)); else echo "  FAIL rc=$RC 字节=$B 正文字数=$BL(空/报错)"; FAILED="$FAILED $V"; fi
done <<< "$SEL"

cp -f "$TMPD"/*.txt "$KEEP"/ 2>/dev/null
rm -rf "$TMPD"
if [ $DRY = 1 ]; then echo "[dry-run] 结束"; exit 0; fi
if [ -f "$LEDGER" ]; then
  printf '| %s | %s | %s | %s/%s |%s\n' "$(date '+%F %H:%M')" "$TASK" "$VNAMES" "$OK" "$N" "$([ -z "$FAILED" ] && echo ' 全部完成' || echo " 未完成:$FAILED")" >> "$LEDGER"
fi
echo "输出: $KEEP"
if [ "$OK" = "$N" ]; then
  echo "[结论] $N 家全部真跑完"
  MODELS=$(grep -o '\[[a-zA-Z]*\] [^ ]*' "${OUT:-/dev/null}" 2>/dev/null | awk '{print $2}' | paste -sd, -)
  [ -n "$MODELS" ] && python3 "$(dirname "$0")/landing-gate.py" record --task "$PROMPT" --models "$MODELS" --verdicts "$(printf 'GO,%.0s' $(seq 1 $N) | sed 's/,$//')" 2>/dev/null | head -2
  python3 "$(dirname "$0")/eval-ledger.py" import >/dev/null 2>&1 || echo "（账本同步失败，已记日志）" >&2
  exit 0
fi
echo "[结论] 未跑完 →$FAILED ；不采信单边"
exit 3
