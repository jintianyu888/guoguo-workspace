#!/bin/bash
# senate-audit.sh - daily independent audit by a rotating senator. Read-only, evidence-based.
set -uo pipefail
WS=/home/j/.openclaw/workspace
OC=/home/j/.npm-global/bin/openclaw
D=$(date +%F)
MODE=${1:-run}
LOG=$WS/state/senate/audit.log
mkdir -p $WS/state/senate $WS/state/work/senate-audit
REPORT=$WS/state/work/senate-audit/$D.md

SEAT_MODEL=$(python3 - <<'PY'
import json, os, datetime
rot = json.load(open('/home/j/.openclaw/workspace/state/senate/rotation.json'))
w = int(datetime.datetime.now().strftime('%w'))
key = rot['roster'][w % len(rot['roster'])]
if key == 'random':
    pool = rot['random_pool']
    key = pool[int.from_bytes(os.urandom(1), 'big') % len(pool)]
print(key + '|' + rot['seats'].get(key, rot['seats'][rot['fallback']]))
PY
)
SEAT=${SEAT_MODEL%%|*}
MODEL=${SEAT_MODEL##*|}

if [ -n "${SEAT_FORCE:-}" ]; then
  MODEL=$(python3 -c "import json;print(json.load(open('$WS/state/senate/rotation.json'))['seats'].get('$SEAT_FORCE',''))")
  [ -n "$MODEL" ] || { echo "[$(date '+%F %T')] bad SEAT_FORCE=$SEAT_FORCE" >> $LOG; exit 2; }
  SEAT="forced-$SEAT_FORCE"
fi
echo "[$(date '+%F %T')] seat=$SEAT model=$MODEL mode=$MODE" >> $LOG

if [ "$MODE" = "dry" ]; then echo "seat=$SEAT model=$MODEL"; exit 0; fi

PACK=$WS/state/senate/pack-$D.md
python3 $WS/tools/senate-pack.py $PACK >> $LOG 2>&1 || { echo "[$(date '+%F %T')] pack FAILED" >> $LOG; exit 3; }

PROMPT=$WS/state/senate/prompt-$D.md
cat > $PROMPT <<'PROMPTEOF'
你是本机独立审计议员。今天你审计「果果」的决策与工作，以及五大管家（maint/backup/model/work/hermess）的每日自审。

## 身份与边界
- 你不属于被审计方，不参与执行。只读：不修改文件、不重启服务、不对外发送。
- 你没有工具权限，只能基于下面给出的证据包做判断。

## 输入
证据包（原始件，不是别人写的自评）在文件里，请先读：__PACK__
包内含：近 24h 工作日志、未结任务、提案台账、重启日志、失败单元、告警、五大管家自审原文、定时任务投递状态、闭环缺口扫描。

## 审计要求
1. 只以证据包为准。重点找四类问题：说了做了但无证据；有产出无落地；有落地无验收；自审自查同一人。
2. 每条发现必须带证据（引原始行或文件名 + 关键片段）。无证据的判断直接删掉。
3. 分级：P0 数据/安全/不可逆；P1 已发生可修；P2 机制漏洞；P3 改进建议。
4. 必须写出「果果可能没意识到的盲点」至少 2 条，这是本次审计的核心价值。
5. 不要复述证据包，不要夸奖，不要给总分。

## 输出
直接输出报告正文（Markdown，从第一行开始，不要前言，不要用代码围栏包住整篇）：
# 议员审计 __DATE__（席位：__SEAT__）
## 结论（三行以内）
## 发现（P0→P3，每条：问题 / 证据 / 影响 / 建议动作）
## 被审计方可能漏掉的盲点（至少 2 条）
## 需主公拍板（有则列，无则写「无」）
PROMPTEOF

sed -i "s|__PACK__|$PACK|" $PROMPT
sed -i "s|__SEAT__|$SEAT|g" $PROMPT
sed -i "s|__DATE__|$D|" $PROMPT

run_once() {
  local model="$1" attempt=1
  while [ $attempt -le 3 ]; do
    env -u OPENCLAW_SHELL -u OPENCLAW_CLI -u OPENCLAW_SYSTEMD_UNIT -u OPENCLAW_GATEWAY_SERVICE_PID \
      timeout 900 $OC agent --agent maint --session-key "agent:maint:senate-$D-a$attempt" --model "$model" \
      --message-file $PROMPT > "$REPORT" 2>> $LOG
    local rc=$?
    local sz=$(stat -c %s "$REPORT" 2>/dev/null || echo 0)
    if [ "$sz" -gt 600 ]; then return 0; fi
    echo "[$(date '+%F %T')] attempt $attempt rc=$rc bytes=$sz retrying in 90s" >> $LOG
    attempt=$((attempt+1))
    [ $attempt -le 3 ] && sleep 90
  done
  return 1
}

if run_once "$MODEL"; then RC=0; else
  echo "[$(date '+%F %T')] seat $SEAT failed, retry with fallback" >> $LOG
  FB=$(python3 -c "import json;print(json.load(open('$WS/state/senate/rotation.json'))['seats'][json.load(open('$WS/state/senate/rotation.json'))['fallback']])")
  SEAT="fallback-$SEAT"; MODEL=$FB
  run_once "$MODEL" && RC=0 || RC=1
fi

SZ=$(stat -c %s "$REPORT" 2>/dev/null || echo 0)
if [ "$SZ" -gt 600 ]; then
  echo "[$(date '+%F %T')] OK seat=$SEAT bytes=$SZ rc=$RC" >> $LOG
  exit 0
fi
echo "[$(date '+%F %T')] NO REPORT seat=$SEAT bytes=$SZ rc=$RC" >> $LOG
exit 4

