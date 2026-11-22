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

# 2026-11-22 主公令：淘金币冻结，标记文件存在即跳过
if [ -f "$WS/state/phone/taobao-frozen" ]; then echo "$(date -Is) FROZEN skip" >> "$LOG"; exit 0; fi
echo "$(date -Is) RUN start" >> "$LOG"
bash "$SCRIPTS/kola-onetap.sh" >> "$LOG" 2>&1
rc=$?
# 主路径 Kola 失败 → 退到直连淘宝，至少保证当日签到
if [ "$rc" != "0" ]; then
  echo "$(date -Is) Kola 失败 rc=$rc，退直连淘宝签到" >> "$LOG"
  bash "$SCRIPTS/taobao-coin.sh" >> "$LOG" 2>&1
  rc2=$?
  [ "$rc2" = "0" ] && rc=0
fi
# 失败不标 done，最多重试 3 次后放弃（避免无限重试）
if [ "$rc" != "0" ]; then
  att=$(python3 -c "import json;print(json.load(open('$STATE')).get('attempts',0))")
  att=$((att+1))
  python3 - "$STATE" "$att" <<'PY'
import json,sys
p,a=sys.argv[1],int(sys.argv[2])
d=json.load(open(p)); d['attempts']=a
if a>=3: d['done']=True
d['rc']=1
json.dump(d,open(p,'w'))
PY
  echo "$(date -Is) RUN fail rc=$rc attempts=$att" >> "$LOG"
  exit 0
fi
python3 - "$STATE" "$rc" <<'PY'
import json,sys
state,rc=sys.argv[1],sys.argv[2]
d=json.load(open(state)); d['done']=True; d['rc']=int(rc)
json.dump(d,open(state,'w'))
PY
echo "$(date -Is) RUN end rc=$rc" >> "$LOG"
tail -n 500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
exit 0
