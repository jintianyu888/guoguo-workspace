#!/bin/sh
# dl-status.sh v2 —— 下载状态行（含「卡住」判定；绝不再隐藏）
W=/home/j/.openclaw/workspace
D=$W/state/dl
TGT=1324
[ -d "$D" ] || { echo "⬇️ 下载：无"; exit 0; }
SZ=$(du -sm "$D" 2>/dev/null | cut -f1); SZ=${SZ:-0}
NEW=$(ls -t "$D"/* 2>/dev/null | head -n 1)
M=9999
[ -n "$NEW" ] && M=$(( ( $(date +%s) - $(stat -c %Y "$NEW" 2>/dev/null || date +%s) ) / 60 ))
P=$(pgrep -c -f 'wget' 2>/dev/null); P=${P:-0}
Q=$(pgrep -c -f 'multi-dl' 2>/dev/null); Q=${Q:-0}
WHL=$(ls "$D"/*.whl 2>/dev/null | wc -l)
PCT=$(( SZ * 100 / TGT ))
if [ "$WHL" -ge 2 ]; then
  echo "⬇️ 下载：已完成 ✅"
elif [ "$((P+Q))" -eq 0 ] && [ "$M" -ge 10 ]; then
  echo "⬇️ 下载：🔴 卡住（${M} 分钟无增长·无进程）→ 已切限次重试（包非必需）"
elif [ "$M" -ge 20 ]; then
  echo "⬇️ 下载：🔴 卡住（${M} 分钟无增长）→ 正在诊断"
else
  echo "⬇️ 下载：进行中 ${SZ}/${TGT}MB（${PCT}%）· 进程 $((P+Q)) 个 · ${M} 分钟前有写入"
fi