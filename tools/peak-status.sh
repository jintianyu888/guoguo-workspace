#!/bin/sh
# DeepSeek 时段提醒（2026-10-24 校准：以官方价格页原文为准）
# 官方原文："Peak hours are 01:00 - 04:00 and 06:00 - 10:00 UTC, Monday through Friday,
#            excluding Chinese public holidays. All other hours are off-peak,
#            including weekends and Chinese public holidays in full."
# 换算北京时间（UTC+8）：
#   高峰 = 周一至周五 09:00-12:00 与 14:00-18:00（不含中国法定节假日）
#   其余（含整周末、法定节假日全天）= 闲时，半价
# 用法: sh tools/peak-status.sh

LEAD=30
dow=$(date +%u)
hm=$(date +%H%M)
h=$(echo "$hm" | cut -c1-2 | sed "s/^0//"); [ -z "$h" ] && h=0
m=$(echo "$hm" | cut -c3-4 | sed "s/^0//"); [ -z "$m" ] && m=0
now=$((h * 60 + m))
fmt() { printf "%02d:%02d" $(( $1 / 60 )) $(( $1 % 60 )); }
inwin() { [ $1 -ge $2 ] && [ $1 -lt $3 ]; }
HOLFILE="$(dirname "$0")/../state/holidays.txt"
IS_HOL=0; HNAME=""
if [ -f "$HOLFILE" ] && grep -qE "^$(date +%Y-%m-%d)([[:space:]]|$)" "$HOLFILE" 2>/dev/null; then
  IS_HOL=1
  HNAME=$(grep -E "^$(date +%Y-%m-%d)([[:space:]]|$)" "$HOLFILE" | head -1 | awk '{print $2}')
fi
if [ "$dow" -ge 6 ]; then
  echo "🟢 现在【周末·全天半价】DeepSeek 闲时｜下个高峰：下周一 09:00"
  echo "   建议：重活放心跑 ✅"
  exit 0
fi
if [ "$IS_HOL" = "1" ]; then
  echo "🟢 现在【法定节假日·全天半价】 $HNAME ｜下个高峰：节后工作日 09:00"
  echo "   建议：今天整天都便宜，重活可以放心跑 ✅"
  exit 0
fi
P1S=540; P1E=720; P2S=840; P2E=1080
if inwin $now $P1S $P1E; then
  left=$((P1E - now)); lbl=$(fmt $P1E)
  echo "🔴 现在【高峰·全价】DeepSeek 工作日高峰｜$(fmt $left) 后转闲时（$lbl）"
  exit 0
fi
if inwin $now $P2S $P2E; then
  left=$((P2E - now)); lbl=$(fmt $P2E)
  echo "🔴 现在【高峰·全价】DeepSeek 工作日高峰｜$(fmt $left) 后转闲时（$lbl）"
  exit 0
fi
if [ $now -lt $P1S ]; then nx=$P1S; lbl="09:00"
elif [ $now -lt $P2S ]; then nx=$P2S; lbl="14:00"
else nx=1440; lbl="次日 00:00"; fi
left=$((nx - now))
echo "🟢 现在【闲时·半价】DeepSeek 非高峰时段｜下个高峰：$lbl（$(fmt $left) 后）"
if [ $left -le $LEAD ]; then echo "   ⏰ 提醒：$(fmt $left) 后进入全价时段，重活尽量现在跑完"; fi
