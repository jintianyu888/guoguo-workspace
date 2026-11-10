#!/bin/bash
# net-watch.sh v1.1 — 断网监控（2026-10-30 三审定案：MiniMax-M3 终审参数）
set -uo pipefail
WS=/home/j/.openclaw/workspace
ST=${NETWATCH_STATE:-$WS/state/work/net-watch.json}
LOG=${NETWATCH_LOG:-$WS/state/net-watch.jsonl}
mkdir -p "$(dirname "$ST")" "$(dirname "$LOG")"
now=$(date +%s); hm=$(date +%H%M)

notify(){
  if [ "${NETWATCH_NOTIFY_DRY:-0}" = "1" ]; then echo "[DRY] $*"; return 0; fi
  timeout 90 bash "$WS/tools/notify.sh" "$@" >/dev/null 2>&1
}
probe(){
  [ "${NETWATCH_FORCE_DOWN:-0}" = "1" ] && return 1
  timeout 6 curl -s -o /dev/null --max-time 5 "$1"
}

online=0; detail=""
probe http://223.5.5.5/ && online=1 || detail="$detail 223.5.5.5"
probe http://119.29.29.29/ && online=1 || detail="$detail 119.29"
probe https://www.baidu.com/ && online=1 || detail="$detail baidu"

fail=0; ok=0; alerting=0; last_alert=0; alerts=0; down_since=0
if [ -f "$ST" ]; then
  read fail ok alerting last_alert alerts down_since < <(python3 - "$ST" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
print(d.get("fail",0), d.get("ok",0), d.get("alerting",0), d.get("last_alert",0), d.get("alerts",0), d.get("down_since",0))
PY
  )
fi
fail=${fail:-0}; ok=${ok:-0}; alerting=${alerting:-0}; last_alert=${last_alert:-0}; alerts=${alerts:-0}; down_since=${down_since:-0}

quiet=0
if [ "$hm" -ge 430 ] && [ "$hm" -lt 530 ]; then quiet=1; fi
act="none"

if [ "$online" -eq 1 ]; then
  ok=$((ok+1)); fail=0
  if [ "$alerting" -eq 1 ] && [ "$ok" -ge 2 ]; then
    dur=$(( (now - down_since) / 60 ))
    notify "🌐 网络已恢复（中断约 ${dur} 分钟）"
    alerting=0; alerts=0; down_since=0; act="recovered"
  fi
else
  fail=$((fail+1)); ok=0
  if [ "$down_since" -eq 0 ]; then down_since=$now; fi
  if [ "$quiet" -eq 1 ]; then
    if [ "$fail" -ge 10 ] && [ "$alerting" -eq 0 ]; then
      notify --alert "⚠️ 告警｜凌晨断网未按惯例恢复（已约 $((fail*3)) 分钟），请检查光猫/线路"
      alerting=1; alerts=1; last_alert=$now; act="quiet-alert"
    fi
  else
    if [ "$fail" -ge 4 ] && [ "$alerting" -eq 0 ]; then
      notify --alert "⚠️ 告警｜断网：连续 4 次探测失败（约 12 分钟），失败目标:${detail}"
      alerting=1; alerts=1; last_alert=$now; act="alert"
    elif [ "$alerting" -eq 1 ] && [ "$alerts" -lt 3 ] && [ $(( (now - last_alert) / 60 )) -ge 30 ]; then
      notify --alert "⚠️ 告警｜断网仍在持续（已约 $(( (now - down_since) / 60 )) 分钟）"
      alerts=$((alerts+1)); last_alert=$now; act="re-alert"
    fi
  fi
fi

if [ "$quiet" -eq 0 ] && [ "$hm" -ge 530 ] && [ "$hm" -lt 600 ] && [ "$fail" -ge 10 ] && [ "$alerting" -eq 0 ]; then
  notify --alert "⚠️ 告警｜凌晨断网持续到 05:30 仍未恢复"
  alerting=1; alerts=1; last_alert=$now; act="dawn-alert"
fi

python3 - "$ST" "$fail" "$ok" "$alerting" "$last_alert" "$alerts" "$down_since" <<'PY'
import json,sys,os
st=sys.argv[1]
v={"fail":int(sys.argv[2]),"ok":int(sys.argv[3]),"alerting":int(sys.argv[4]),
   "last_alert":int(sys.argv[5]),"alerts":int(sys.argv[6]),"down_since":int(sys.argv[7])}
tmp=st+".tmp"
with open(tmp,"w") as f:
    json.dump(v,f); f.flush(); os.fsync(f.fileno())
os.replace(tmp,st)
PY

printf '{"at":"%s","online":%s,"fail":%s,"action":"%s","failed":"%s"}\n' "$(date '+%F %T')" "$online" "$fail" "$act" "$detail" >> "$LOG"
echo "$(date '+%F %T') online=$online fail=$fail act=$act"