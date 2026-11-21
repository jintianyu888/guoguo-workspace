#!/usr/bin/env bash
# R27 检查：近 30 天有升级运行记录；升级日志里有经验闸门；技能当天回写提示未堆积
set -u
W=/home/j/.openclaw/workspace
RUNS=/home/j/.openclaw/shared-skills/openclaw-upgrade/references/runs.md
FAIL=0
if [ ! -f "$RUNS" ]; then echo "FAIL 无运行记录文件 $RUNS"; FAIL=1; else
  N=$(grep -c "^| 20" "$RUNS" 2>/dev/null || echo 0)
  [ "$N" -ge 1 ] || { echo "FAIL 运行记录为空"; FAIL=1; }
fi
LOG=$W/state/work/upgrade-panel.log
if [ -f "$LOG" ] && ! grep -q "经验闸门" "$LOG"; then echo "FAIL 升级日志无经验闸门回执（先跑 bash tools/exp-gate.sh 升级）"; FAIL=1; fi
PEND=$W/state/skills/pending-upgrade-skill.txt
if [ -s "$PEND" ]; then echo "WARN 有待回写的升级技能提醒 $(wc -l < "$PEND") 条：$PEND"; fi
[ "$FAIL" = "0" ] && echo "PASS R27 升级复用与技能回写"
exit "$FAIL"