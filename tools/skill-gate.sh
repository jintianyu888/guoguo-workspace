#!/usr/bin/env bash
# skill-gate.sh —— 开工先查技能（2026-11-21 主公令·所有管家硬性）
# 用法：bash tools/skill-gate.sh "<任务关键词>" [--agent <id>]
# 作用：一次搜三处（共享技能 / 经验条目 / tools 脚本），打印命中，并落回执到 state/skills/lookups/
set -u
W=/home/j/.openclaw/workspace
KW="${1:-}"; AG="${SKILL_GATE_AGENT:-${OPENCLAW_AGENT_ID:-unknown}}"
shift 2>/dev/null || true
while [ $# -gt 0 ]; do case "$1" in --agent) AG="$2"; shift 2;; *) shift;; esac; done
[ -z "$KW" ] && { echo "usage: bash tools/skill-gate.sh \"<关键词>\" [--agent id]"; exit 2; }
TS=$(date +%Y%m%d-%H%M%S)
DIR=$W/state/skills/lookups; mkdir -p "$DIR"

echo "══ 技能闸门：$KW（agent=$AG） ══"
echo "-- 1) 共享技能（~/ .openclaw/shared-skills）"
SH=$(ls -1 /home/j/.openclaw/shared-skills 2>/dev/null | grep -i -- "$KW" | head -6)
if [ -n "$SH" ]; then echo "$SH" | sed "s/^/   ✅ /"; else echo "   （无同名技能，试看描述命中）"; grep -ril --include=SKILL.md -- "$KW" /home/j/.openclaw/shared-skills 2>/dev/null | head -4 | sed "s#/home/j/.openclaw/shared-skills/##;s#/SKILL.md##;s/^/   ~ /"; fi

echo "-- 2) 技能库·经验条目（tools/exp.py）"
EXP=$(timeout 60 python3 "$W/tools/exp.py" "$KW" 2>/dev/null | head -12)
printf "%s\n" "$EXP" | sed -n "1,8p" | sed "s/^/   /"

echo "-- 3) 现成脚本（tools/）"
ls -1 "$W/tools" 2>/dev/null | grep -i -- "$KW" | head -6 | sed "s/^/   ⚙ /"
grep -ril --include=*.sh --include=*.py -- "$KW" "$W/tools" 2>/dev/null | head -6 | sed "s#$W/tools/#   ~ #"

N_SH=$(printf "%s" "$SH" | grep -c . || true)
N_EX=$(printf "%s\n" "$EXP" | grep -c "^- \[" || true)
REC="$DIR/$TS-$AG.json"
python3 - "$REC" "$AG" "$KW" "$N_SH" "$N_EX" <<PY
import json,sys
rec,ag,kw,ns,ne=sys.argv[1:6]
json.dump({"ts":rec.split("/")[-1][:-5],"agent":ag,"keyword":kw,"skills":int(ns or 0),"exp_hits":int(ne or 0)}, open(rec,"w"), ensure_ascii=False)
PY
echo "-- 回执：$REC"
echo "══ 命中即复用；没命中才自己写，写完必须沉淀成技能 ══"
exit 0