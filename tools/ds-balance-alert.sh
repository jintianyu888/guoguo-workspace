#!/bin/sh
# ds-balance-alert.sh —— 余额获取 + 预警（阈值：$15 / ¥50）
# 输出规则：低于阈值 → 打印提醒（供 automation announce）；正常 → 不输出
# 数据源优先级：① provider usage（openclaw status --usage） ② env 类密钥直连 DeepSeek 余额接口 ③ 上次已知余额 - 期间花费（估算）
set -u
WS=/home/j/.openclaw/workspace
ST="$WS/state/ds-balance-state.json"
BAL=""; CUR=""

# ① provider usage
u=$(timeout 20 openclaw status --usage 2>/dev/null)
bal=$(printf "%s" "$u" | grep -oE "[$¥][0-9]+(\.[0-9]+)?" | head -1)
if [ -n "$bal" ]; then BAL=$(printf "%s" "$bal" | tr -d "$¥"); case "$bal" in "¥"*) CUR=CNY;; *) CUR=USD;; esac; fi

# ② env 类密钥直连（密钥在密钥库，脚本内使用、不落盘、不回显）
if [ -z "$BAL" ]; then
  k=$(timeout 10 openclaw secrets store get DEEPSEEK_KEY_68_ENV --plain 2>/dev/null || true)
  if [ -n "$k" ]; then
    j=$(timeout 20 curl -s -H "Authorization: Bearer $k" https://api.deepseek.com/user/balance 2>/dev/null)
    unset k
    BAL=$(printf "%s" "$j" | grep -oE "\"total_balance\":\"?[0-9.]+" | grep -oE "[0-9.]+" | head -1)
    CUR=$(printf "%s" "$j" | grep -oE "\"currency\":\"[A-Z]+" | grep -oE "[A-Z]+" | head -1)
    [ -n "$CUR" ] || CUR=CNY
  fi
fi

# ③ 估算兜底：上次已知余额 - 期间开销
if [ -z "$BAL" ]; then
  prev=$(timeout 10 sh -c "grep -oE \"balance\":[0-9.]+ \"$ST\" 2>/dev/null | head -1" || true)
  [ -n "$prev" ] && { BAL=$(printf "%s" "$prev" | grep -oE "[0-9.]+"); CUR=EST; }
fi

now=$(date "+%Y-%m-%d %H:%M")
# 瞬时失败重试（secrets CLI 超时是常见假警报源）
if [ -z "$BAL" ]; then
  i=0
  while [ $i -lt 3 ]; do
    b=$(sh "$WS/tools/ds-balance.sh" 2>/dev/null | grep -oE '[0-9]+(\.[0-9]+)?' | head -1)
    if [ -n "$b" ]; then BAL="$b"; CUR=CNY; break; fi
    i=$((i+1)); sleep 3
  done
fi
if [ -z "$BAL" ]; then
  FC="$WS/state/ds-balance-alert-failcount"
  n=$(cat "$FC" 2>/dev/null || echo 0)
  n=$((n+1)); printf "%s" "$n" > "$FC"
  if [ "$n" -ge 2 ]; then
    echo "⚠️ 余额预警：连续 $n 次取不到余额（重试 3 次仍失败）· $now · 需检查密钥"
  fi
  exit 0
fi
rm -f "$WS/state/ds-balance-alert-failcount"

low=0
case "$CUR" in
  USD) awk "BEGIN{exit !($BAL<15)}" && low=1 ;;
  CNY|EST) awk "BEGIN{exit !($BAL<50)}" && low=1 ;;
esac
if [ "$low" = 1 ]; then
  printf "🔴 余额预警：DeepSeek 余额仅剩 %s%s（阈值：\$15 / ¥50）· %s · 建议尽快充值\n" "$CUR" "$BAL" "$now"
fi