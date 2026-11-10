#!/usr/bin/env bash
# otp.sh —— 一次性验证码（本地生成/校验，用完即废）
# 用途：敏感操作前验证主人身份（配合声纹+口令，三层之一）
# 用法: otp.sh new [分钟]      生成新码（默认5分钟有效）
#       otp.sh check <码>      校验
#       otp.sh show            查看当前有效码（仅本机，用于抄到纸上/群晖）
D=/home/j/.openclaw/workspace/state; F=$D/.otp; mkdir -p $D
case "${1:-}" in
  new)
    M=${2:-5}; CODE=$(shuf -i 100000-999999 -n 1)
    printf '%s|%s\n' "$CODE" "$(( $(date +%s) + M*60 ))" > "$F"; chmod 600 "$F"
    echo "一次性码：$CODE（$(date '+%H:%M') 起 ${M} 分钟内有效，用一次即废）" ;;
  show)
    [ -f "$F" ] || { echo '当前没有有效码'; exit 1; }
    IFS='|' read -r C E < "$F"
    [ "$(date +%s)" -lt "$E" ] && echo "当前码：$C（有效至 $(date -d @$E '+%H:%M')）" || echo '已过期' ;;
  check)
    G=${2:-}; [ -f "$F" ] || { echo '❌ 没有待验的码'; exit 1; }
    IFS='|' read -r C E < "$F"
    if [ "$(date +%s)" -ge "$E" ]; then echo '❌ 已过期'; rm -f "$F"; exit 1; fi
    if [ "$G" = "$C" ]; then echo '✅ 验证通过（码已作废）'; rm -f "$F"; else echo '❌ 不匹配'; fi ;;
  *) echo '用法: otp.sh new [分钟] | check <码> | show' ;;
esac
