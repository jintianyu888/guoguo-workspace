#!/usr/bin/env bash
# R28 检查：开工先查技能（2026-11-21 主公令）
set -u
W=/home/j/.openclaw/workspace
FAIL=0
[ -x "$W/tools/skill-gate.sh" ] || { echo "FAIL 缺 tools/skill-gate.sh"; FAIL=1; }
TOT=$(ls -d /home/j/openclaw-workspaces/*/ 2>/dev/null | wc -l)
HIT=$(grep -l "开工先查技能" /home/j/openclaw-workspaces/*/AGENTS.md 2>/dev/null | wc -l)
[ "$TOT" -ge 30 ] || { echo "FAIL 管家工作区数异常（$TOT）"; FAIL=1; }
[ "$HIT" -ge "$TOT" ] || { echo "FAIL 守则未覆盖全部管家（$HIT/$TOT），跑 bash tools/agent-common-sync.sh --apply"; FAIL=1; }
REC=$(find "$W/state/skills/lookups" -name "*.json" -newermt "-24 hours" 2>/dev/null | wc -l)
[ "$REC" -ge 1 ] || echo "WARN 近 24h 无技能查询回执（state/skills/lookups/），开工记得 bash tools/skill-gate.sh \"<关键词>\""
[ "$FAIL" = "0" ] && echo "PASS R28 开工先查技能（覆盖 $HIT/$TOT，24h 回执 $REC 条）"
exit "$FAIL"