#!/bin/bash
# 每天在随机时刻执行一次手机淘宝任务（默认 07:00-23:00 窗口内随机）
# 由 oc-phone-tasks.timer 每 15 分钟触发一次，本脚本负责「今天该不该跑、到点没到点」
set -u
WS=/home/j/.openclaw/workspace
STATE="$WS/state/phone/plan.json"
LOG="$WS/state/phone/scheduler.log"
SCRIPTS="$WS/tools"
mkdir -p "$(dirname "$STATE")"
today=$(date +%F)
now=$(date +%H:%M)

# 允许通过环境变量覆盖窗口
WIN_START=${WIN_START:-07:00}
WIN_END=${WIN_END:-23:00}

python3 - "$STATE" "$today" "$WIN_START" "$WIN_END" <<'PY' > /tmp/plan.out
import json,os,random,sys
state,today,ws,we=sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4]
def m(t):
    h,mi=t.split(':'); return int(h)*60+int(mi)
try:
    d=json.load(open(state))
except Exception:
    d={}
if d.get('date')!=today:
    a,b=m(ws),m(we)
    t=random.randint(a,b-1)
    d={'date':today,'target':'%02d:%02d'%(t//60,t%60),'done':False}
    json.dump(d,open(state,'w'))
print(json.dumps(d,ensure_ascii=False))
PY
plan=$(cat /tmp/plan.out)
target=$(printf '%s' "$plan" | python3 -c 'import json,sys;print(json.load(sys.stdin)["target"])')
done=$(printf '%s' "$plan" | python3 -c 'import json,sys;print(json.load(sys.stdin)["done"])')

echo "$(date -Is) now=$now target=$target done=$done" >> "$LOG"

if [ "$done" = "True" ]; then exit 0; fi
if [ "$now" \< "$target" ]; then exit 0; fi

echo "$(date -Is) RUN start" >> "$LOG"
python3 "$SCRIPTS/phone-kola-task.py" >> "$LOG" 2>&1
rc=$?
python3 - "$STATE" "$rc" <<'PY'
import json,sys
state,rc=sys.argv[1],sys.argv[2]
d=json.load(open(state)); d['done']=True; d['rc']=int(rc)
json.dump(d,open(state,'w'))
PY
echo "$(date -Is) RUN end rc=$rc" >> "$LOG"
tail -n 500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
exit 0
