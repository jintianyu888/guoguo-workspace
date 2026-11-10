#!/bin/bash
# assistant-weekly-health.sh v1.2 — 果果助手 周体检（含审核链 + Kimi K3.1 Pro）
set -u -o pipefail
WS=/home/j/.openclaw/workspace
BAT=/mnt/c/Users/J/Desktop/果果助手.bat
OUT=$WS/state/desktop-console
mkdir -p "$OUT"
LOG=$OUT/weekly-health.log
STAMP=$(date '+%F %T')
P=0; W=0; F=0; ROWS=""
row(){ local s="$1" n="$2" d="$3"; ROWS="$ROWS$s|$n|$d\n"; case "$s" in PASS) P=$((P+1));; WARN) W=$((W+1));; FAIL) F=$((F+1));; esac; }
PROMPT_TXT="只回一行 OK"

if [ -f "$BAT" ]; then
  SZ=$(stat -c %s "$BAT")
  CRLF=$(grep -c $'\r' "$BAT" 2>/dev/null || echo 0)
  BV=$(grep -m1 -oE 'set "VER=[0-9.]+"' "$BAT" | grep -oE '[0-9.]+')
  JV=$(python3 -c "import json;print(json.load(open('$OUT/version.json'))['version'])" 2>/dev/null)
  [ "$CRLF" -gt 100 ] && row PASS "bat 换行" "CRLF 正常 ($SZ 字节)" || row FAIL "bat 换行" "非 CRLF"
  [ -n "$BV" ] && [ "$BV" = "$JV" ] && row PASS "版本一致" "bat=$BV ledger=$JV" || row FAIL "版本一致" "bat=$BV ledger=$JV"
else row FAIL "bat 存在" "桌面找不到果果助手.bat"; fi
LEFTOVER=$(ls /mnt/c/Users/J/Desktop/*.bat 2>/dev/null | grep -v 果果助手.bat | wc -l)
[ "$LEFTOVER" -eq 0 ] && row PASS "桌面整洁" "只剩果果助手.bat" || row WARN "桌面整洁" "还有 $LEFTOVER 个旧 bat"

CC=$WS/tools/console-cmd.sh
if bash -n "$CC" 2>/dev/null; then row PASS "分发器语法" "OK"; else row FAIL "分发器语法" "语法错误"; fi
for v in status quota cfgroll; do
  if timeout 60 bash "$CC" "$v" >/dev/null 2>&1; then row PASS "命令:$v" "可用"; else row FAIL "命令:$v" "调用失败"; fi
done

CG=$(grep -c 'call :CONFIRM' "$BAT" 2>/dev/null || true); CG=${CG:-0}
[ "$CG" -ge 4 ] && row PASS "危险项确认" "$CG 处二次确认" || row FAIL "危险项确认" "只有 $CG 处"
grep -q 'clean-dry' "$BAT" && ! grep -q 'clean-real' "$BAT" && row PASS "清理只预演" "无真删入口" || row FAIL "清理只预演" "发现真删入口"
grep -q 'json.bad-' "$CC" && row PASS "配置回滚留底" "恢复前先存 .bad" || row WARN "配置回滚留底" "未见留底"

AL=$OUT/actions.log
if [ -f "$AL" ]; then
  AS=$(stat -c %s "$AL")
  [ "$AS" -lt 2097152 ] && row PASS "操作留痕" "$(wc -l < "$AL") 行 / $AS 字节" || row WARN "操作留痕" "$AS 字节建议归档"
else row WARN "操作留痕" "actions.log 尚未生成"; fi

CR=$WS/tools/cross-review.sh
if bash -n "$CR" 2>/dev/null; then row PASS "审核器语法" "OK"; else row FAIL "审核器语法" "语法错误"; fi
POOLN=$(grep -oE '"(deepseek|zhipu|kimi|minimax)\|' "$CR" | sort -u | wc -l)
[ "$POOLN" -eq 4 ] && row PASS "厂商池" "4 家齐全" || row FAIL "厂商池" "只有 $POOLN 家"
grep -q 'kimi-k3.1-pro' "$CR" && row PASS "最新模型入库" "K3.1 Pro 在池" || row WARN "最新模型入库" "未用 K3.1 Pro"
bash "$CR" --dry-pick >/dev/null 2>&1 && row PASS "随机抽取" "dry-pick 可用" || row FAIL "随机抽取" "dry-pick 失败"
if [ -f "$WS/docs/交叉验证台账.md" ]; then
  AGE=$(( ( $(date +%s) - $(stat -c %Y "$WS/docs/交叉验证台账.md") ) / 86400 ))
  [ "$AGE" -le 14 ] && row PASS "审核台账" "$AGE 天前更新" || row WARN "审核台账" "$AGE 天未更新"
else row WARN "审核台账" "台账缺失"; fi

probe(){
  local m="$1" t="${2:-}"
  if [ -n "$t" ]; then
    timeout 220 openclaw infer model run --model "$m" --gateway --thinking "$t" --prompt "$PROMPT_TXT" 2>&1
  else
    timeout 150 openclaw infer model run --model "$m" --gateway --prompt "$PROMPT_TXT" 2>&1
  fi
}
for M in deepseek/deepseek-v4-pro zai/glm-5.3 kimi-coding/kimi-k3.1-pro minimax/MiniMax-M3.1-Flash-Preview; do
  THK=""
  [ "$M" = "kimi-coding/kimi-k3.1-pro" ] && THK=on
  T=$(mktemp)
  probe "$M" "$THK" > "$T"; RC=$?; B=$(wc -c < "$T")
  if [ $RC -ne 0 ] || [ "$B" -lt 20 ]; then probe "$M" "$THK" > "$T"; RC=$?; B=$(wc -c < "$T"); fi
  rm -f "$T"
  if [ $RC -eq 0 ] && [ "$B" -ge 20 ]; then row PASS "模型:$M" "$B 字节"; else row FAIL "模型:$M" "rc=$RC 字节=$B"; fi
done

IW=/home/j/openclaw-workspaces/work/果果助手
if [ -f "$IW/tools/selfcheck.sh" ]; then
  if timeout 180 bash "$IW/tools/selfcheck.sh" >/tmp/iw-selfcheck.log 2>&1; then row PASS "信息窗自检" "通过"
  elif grep -q '^OK' /tmp/iw-selfcheck.log; then row PASS "信息窗自检" "输出OK（退出码异常，日志已留）"
  else row WARN "信息窗自检" "真失败，见 /tmp/iw-selfcheck.log"; fi
else row WARN "信息窗自检" "脚本缺失"; fi
CARD=$WS/state/info-window/card.png
if [ -f "$CARD" ]; then
  HAGE=$(( ( $(date +%s) - $(stat -c %Y "$CARD") ) / 3600 ))
  [ "$HAGE" -le 24 ] && row PASS "信息窗卡片" "$HAGE h 前渲染" || row WARN "信息窗卡片" "$HAGE h 未更新"
else row WARN "信息窗卡片" "card.png 缺失"; fi

SUM="PASS $P / WARN $W / FAIL $F"
printf '%s %s\n' "$STAMP" "$SUM" >> "$LOG"
{ echo "果果助手 周体检 $STAMP"; echo "$SUM"; echo; printf "$ROWS" | while IFS='|' read -r s n d; do [ -n "$s" ] && printf '%-4s %-16s %s\n' "$s" "$n" "$d"; done; } > "$OUT/weekly-health.txt"
cat "$OUT/weekly-health.txt"
if [ "$F" -gt 0 ]; then
  timeout 30 bash "$WS/tools/notify.sh" --alert "【告警】果果助手周体检 $SUM" "$(grep '^FAIL' "$OUT/weekly-health.txt" | head -6 | tr '\n' ';')" >/dev/null 2>&1 || true
fi
exit 0
