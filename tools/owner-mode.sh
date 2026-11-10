#!/bin/bash
# 主公在场判定：最近 15 分钟有交互=hot（只做主公的活），否则=idle（可跑后台计划）
F=/home/j/.openclaw/workspace/state/work/owner-last-seen
[ -f "$F" ] || { echo idle; exit 0; }
AGE=$(( $(date +%s) - $(stat -c %Y "$F") ))
if [ "$AGE" -lt 900 ]; then echo hot; else echo idle; fi
