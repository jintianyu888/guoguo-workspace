#!/usr/bin/env bash
# restart-acceptance.sh v1 —— 重启四项验收（2026-10-31 双审必改项落地）
# 用法: restart-acceptance.sh [旧PID]  → 结果写 state/work/restart-acceptance.json，rc=0 全绿
set -uo pipefail
W=/home/j/.openclaw/workspace
PORT=18789
OLD=${1:-0}
OUT=$W/state/work/restart-acceptance.json
NEW=$(timeout 5 systemctl --user show -p MainPID --value openclaw-gateway 2>/dev/null || echo 0)
ACT=$(systemctl --user is-active openclaw-gateway 2>/dev/null || echo unknown)
# 1 PID
if [ "$ACT" = active ] && [ "$NEW" != "0" ] && [ "$NEW" != "$OLD" ]; then R1=ok; else R1=fail; fi
# 2 HTTP
HTTP=000
for i in 1 2 3; do
  HTTP=$(timeout 6 curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health" 2>/dev/null || echo 000)
  [ "$HTTP" = 200 ] && break; sleep 3
done
[ "$HTTP" = 200 ] && R2=ok || R2=fail
# 3 模型链
MCOUT=$(cd "$W" && timeout 60 python3 tools/modelchain-check.py 2>&1); MCRC=$?
[ $MCRC -eq 0 ] && R3=ok || { [ $MCRC -eq 2 ] && R3=unknown || R3=fail; }
# 4 任务层
CRON=$(cd "$W" && timeout 60 openclaw cron list --json 2>/dev/null | python3 -c 'import sys,json;json.load(sys.stdin);print("ok")' 2>/dev/null || echo fail)
[ "$CRON" = ok ] && R4=ok || R4=fail
# 5 会话墓碑（重启副作用）：正在干活的会话会被标记不可恢复，之后该会话的消息全部被拒发
# 只认本次网关启动之后、且明确带 SessionRestartRecoveryTombstoneError 的行；不按“最近 N 分钟”猜
GW_SINCE=$(systemctl --user show -p ActiveEnterTimestamp --value openclaw-gateway 2>/dev/null)
[ -z "$GW_SINCE" ] && GW_SINCE="-20 min"
TMBS=$(journalctl --user -u openclaw-gateway --since "$GW_SINCE" --no-pager 2>/dev/null \
  | grep 'SessionRestartRecoveryTombstoneError' \
  | grep -oE 'agent:[A-Za-z0-9:._-]+' | sort -u | head -5)
TMB_CLEARED=""; TMB_FAILED=""; TMB_GONE=""
if [ -n "$TMBS" ]; then
  CURKEYS=$(timeout 40 openclaw sessions --all-agents --json 2>/dev/null | grep -oE 'agent:[A-Za-z0-9:._-]+' | sort -u)
  while IFS= read -r SK; do
    [ -z "$SK" ] && continue
    if [ -n "$CURKEYS" ] && ! printf '%s\n' "$CURKEYS" | grep -qxF "$SK"; then TMB_GONE="$TMB_GONE $SK"; continue; fi
    AG=${SK#agent:}; AG=${AG%%:*}
    if [ "${TMB_DRY:-0}" = 1 ]; then TMB_CLEARED="$TMB_CLEARED [dry]$SK"; continue; fi
    if timeout 30 openclaw sessions delete --agent "$AG" --yes "$SK" >/dev/null 2>&1; then
      TMB_CLEARED="$TMB_CLEARED $SK"
    else
      TMB_FAILED="$TMB_FAILED $SK"
    fi
  done <<< "$TMBS"
  if [ -n "$TMB_FAILED" ]; then R5=fail; elif [ -n "$TMB_CLEARED" ]; then R5=warn; elif [ -n "$TMB_GONE" ]; then R5=ok; else R5=unknown; fi
else
  R5=ok
fi
VERDICT=ok
for x in $R1 $R2 $R3 $R4 $R5; do [ "$x" = fail ] && VERDICT=fail; done
[ "$VERDICT" = ok ] && for x in $R1 $R2 $R3 $R4 $R5; do { [ "$x" = unknown ] || [ "$x" = warn ]; } && VERDICT=partial; done
TMP=$OUT.tmp
python3 - "$TMP" <<PY
import json,sys,time
json.dump({'ts':time.strftime('%Y-%m-%d %H:%M:%S'),'old_pid':'$OLD','new_pid':'$NEW','active':'$ACT','http':'$HTTP','pid':'$R1','health':'$R2','modelchain':'$R3','cron':'$R4','tombstone':'$R5','tombstone_cleared':'''$TMB_CLEARED'''.strip(),'tombstone_failed':'''$TMB_FAILED'''.strip(),'verdict':'$VERDICT','modelchain_out':'''$MCOUT'''[:800]},open(sys.argv[1],'w'),ensure_ascii=False,indent=1)
PY
mv -f "$TMP" "$OUT"
echo "VERDICT=$VERDICT pid=$R1 health=$R2 modelchain=$R3 cron=$R4 tombstone=$R5 http=$HTTP"
[ "$VERDICT" = ok ] || echo "$MCOUT" | head -5
[ "$VERDICT" = fail ] && exit 3
exit 0
