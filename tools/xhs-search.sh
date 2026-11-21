#!/usr/bin/env bash
# xhs-search.sh / xhs-score.sh —— 小红书随用随查（主公 2026-11-21 令）
# 用途：要菜谱、要乐谱、要查任何东西时临时搜一次即可；不排定时任务，不限次数。
# 用法:
#   xhs-score.sh "红烧肉 做法" --limit 8            # 普通查询
#   xhs-score.sh "起风了" --score --limit 8         # 自动补"钢琴谱"
#   xhs-score.sh "起风了 钢琴谱" --download --out /tmp/xhs
set -u
export DISPLAY=${DISPLAY:-:0}
cd /home/j/.openclaw/workspace || exit 9

KW=""; ARGS=(); SCORE=0
for a in "$@"; do
  case "$a" in
    --score) SCORE=1;;
    --*) ARGS+=("$a");;
    *) if [ -z "$KW" ]; then KW="$a"; else ARGS+=("$a"); fi;;
  esac
done
[ -z "$KW" ] && { echo '{"ok":false,"error":"NO_KEYWORD","hint":"用法: xhs-score.sh \"关键词\" [--score] [--limit 8] [--download]"}'; exit 1; }
if [ "$SCORE" = "1" ]; then
  case "$KW" in *谱*) ;; *) KW="$KW 钢琴谱";; esac
fi
exec node tools/xhs-score.mjs "$KW" "${ARGS[@]}"
