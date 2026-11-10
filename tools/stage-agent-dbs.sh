#!/bin/sh
# stage-agent-dbs.sh —— 把全部管家的原始 sqlite 快照暂存进 backup-extra（随全量归档一起进群晖）
# 2026-09-27 备份审计第5项加固：此前全量归档只覆盖 3/22 个 agent 原始库
set -u
SRC=/home/j/.openclaw/agents
DST=/home/j/.openclaw/backup-extra/agents-db
mkdir -p "$DST"
n=0; tot=0
for d in "$SRC"/*/; do
  a=$(basename "$d"); db="$d/agent/openclaw-agent.sqlite"
  [ -f "$db" ] || continue
  tmp="$DST/$a.sqlite.tmp"
  cp -f "$db" "$tmp" 2>/dev/null || { rm -f "$tmp"; continue; }
  gzip -9 -c "$tmp" > "$DST/$a.sqlite.gz" 2>/dev/null && rm -f "$tmp"
  [ -s "$DST/$a.sqlite.gz" ] && n=$((n+1))
done
tot=$(du -sk "$DST" 2>/dev/null | awk "{print \$1}")
echo "已暂存 $n 个管家原始库 → $DST（合计 ${tot} KB）"