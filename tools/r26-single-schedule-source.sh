#!/usr/bin/env bash
# r26-single-schedule-source.sh —— R26：调度只有一个真源，且自动段是新的
set -u
cd /home/j/.openclaw/workspace || exit 9
T=docs/调度总表-真源.md
[ -f "$T" ] || { echo "R26 违规：缺 $T"; exit 1; }
grep -q '^<!-- AUTO:BEGIN' "$T" || { echo "R26 违规：真源缺自动段标记"; exit 1; }
# 自动段必须 48 小时内刷新
if [ -n "$(find "$T" -mtime +2 2>/dev/null)" ]; then
  echo "R26 违规：真源自动段超 48 小时未刷新，跑 python3 tools/schedule-plan.py report"
  exit 1
fi
# 其他文档不许再自称"唯一真源/以本文件为准"
bad=$(grep -rl '以本文件为准' docs/*.md 2>/dev/null | grep -v '调度总表-真源.md' || true)
if [ -n "$bad" ]; then
  echo "R26 违规：以下文档仍在自称真源，应改成指向真源：$bad"
  exit 1
fi
echo "R26 通过：调度真源唯一（$T）"
