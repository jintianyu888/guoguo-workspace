#!/usr/bin/env bash
# 每周体量自审 + 起止通报(含预估时间)
W=/home/j/.openclaw/workspace
bash $W/tools/notify.sh "▶ 开始：每周体量自审｜预计 1~2 分钟（只读：各盘/目录/vhdx/归档）"
T0=$(date +%s)
OUT=$(bash $W/tools/self-audit.sh 2>&1); RC=$?
T1=$(date +%s); DUR=$((T1-T0))
SUM=$(grep -E '^[0-9.]+[GMT]|vhdx|NAS' "$W/state/self-audit-$(date +%Y%m%d).md" 2>/dev/null | head -6)
bash $W/tools/notify.sh "✅ 结束：每周体量自审｜用时 ${DUR}s｜rc=$RC
${SUM:-（报告见 state/self-audit-*.md）}"
