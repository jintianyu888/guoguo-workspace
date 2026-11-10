#!/bin/sh
# 计算「从收到消息到回复」的耗时。
# 用法: sh elapsed.sh "YYYY-MM-DD HH:MM:SS"
# 输出: 12秒 / 1分23秒 / 1时5分

st="$1"
sec=$(date -d "$st" +%s 2>/dev/null) || { echo "?"; exit 1; }
now=$(date +%s)
d=$((now - sec))
[ "$d" -lt 0 ] && d=0
if [ "$d" -lt 60 ]; then
  echo "${d} 秒"
elif [ "$d" -lt 3600 ]; then
  echo "$((d / 60)) 分 $((d % 60)) 秒"
else
  echo "$((d / 3600)) 时 $(((d % 3600) / 60)) 分"
fi
