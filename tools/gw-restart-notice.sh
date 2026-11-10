#!/usr/bin/env bash
# gw-restart-notice.sh v1 —— 网关重启回执（2026-11-02 主公："你崩了我不知道"）
# 问题：boot-notice.sh 只在「一次开机会话」报一次，同一 boot 内的网关重启全部静默。
#   2026-11-02 实测：当天网关启动 113 次，飞书只收到 1 条开机报平安。
# 做法：每 2 分钟比对 systemd 记录的网关启动时间戳；变了就发一条回执，并判定「计划内/疑似异常」。
#   - 计划内：安全重启单元(safe-restart-*)或 restart-gateway.sh 触发的，带 reason
#   - 疑似异常：systemd 自己拉起（Main process exited / Scheduled restart），高亮报警
set -u
export PATH=/home/j/.npm-global/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace
ST=$W/state/gw-restart-notice
mkdir -p "$ST"
LASTF=$ST/last-start.txt
LOG=$ST/notice.log
LOCK=$ST/.lock
log(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }

exec 9>"$LOCK"
flock -n 9 || exit 0

START=$(systemctl --user show openclaw-gateway -p ExecMainStartTimestamp --value 2>/dev/null)
PID=$(systemctl --user show openclaw-gateway -p MainPID --value 2>/dev/null)
ACT=$(systemctl --user show openclaw-gateway -p ActiveState --value 2>/dev/null)
[ -z "$START" ] && exit 0
KEY="$START|$PID|$ACT"
PREV=$(cat "$LASTF" 2>/dev/null || true)
[ "$KEY" = "$PREV" ] && exit 0
echo "$KEY" > "$LASTF"
[ -z "$PREV" ] && exit 0      # 首次记录只建基线，不播报

PREV_TS=${PREV%%|*}
[ "$PREV_TS" = "$START" ] && exit 0   # 同一启动实例（仅 pid/状态变化），不播报
PREV_PID=$(echo "$PREV" | cut -d"|" -f2)
# 近 10 分钟内的重启原因线索
J=$(journalctl --user -u openclaw-gateway --since "-10 min" --no-pager 2>/dev/null)
KIND="疑似异常重启"; HINT=""
# 2026-11-08 修：重启由独立单元 safe-restart-* 执行，网关 journal 里没有 safe-restart 字样，
# 原来靠 grep journal 会把自己批准的重启误判成「疑似异常」。改以 safe-restart-result.json 为准。
_REST=$W/state/work/safe-restart-result.json
if [ -f "$_REST" ]; then
  _P=$(python3 -c 'import json,sys,datetime
try:
    d=json.load(open(sys.argv[1]))
    ts=datetime.datetime.strptime(d.get("ts",""),"%Y-%m-%d %H:%M:%S")
    if (datetime.datetime.now()-ts).total_seconds() < 1800 and d.get("mode")=="ok":
        print("PLANNED|"+str(d.get("reason","")).replace(chr(10)," ")[:120])
except Exception:
    pass' "$_REST" 2>/dev/null)
  case "$_P" in
    PLANNED*) KIND="计划内重启"; HINT="原因：${_P#PLANNED|}" ;;
  esac
fi
if [ "$KIND" = "疑似异常重启" ] && echo "$J" | grep -qE 'safe-restart|restart-gateway|Stopped OpenClaw Gateway.*reason'; then
  KIND="计划内重启"
  HINT=$(echo "$J" | grep -oE 'reason=[^"]*' | tail -1 | cut -c1-140)
elif echo "$J" | grep -qE 'Main process exited, code=(killed|dumped)|Scheduled restart|watchdog'; then
  HINT=$(echo "$J" | grep -E 'Main process exited|Scheduled restart' | tail -1 | cut -c1-160)
fi
# 启动是否成功（3 次探测 /health）
OK=0
for i in 1 2 3; do
  [ "$(timeout 10 curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/health 2>/dev/null)" = "200" ] && { OK=1; break; }
  sleep 5
done
MSG="【网关重启回执】$(date '+%m-%d %H:%M')
判定：$KIND
上一次启动：$PREV_TS
本次启动：$START（pid $PID，状态 $ACT）
上一次 pid：${PREV_PID:-未知}
健康检查：$([ $OK = 1 ] && echo 'HTTP 200 已就绪' || echo '未就绪，需人工查看')
${HINT:-}"
log "$KIND | $PREV_TS -> $START | pid=$PID health=$OK | $HINT"

# 2026-11-04 台账：每次重启/崩溃落一条结构化记录（供每日归因自查）
REC=$(KIND="${KIND:-未知}" START="${START:-}" PREV="${PREV:-}" PID="${PID:-}" MSG="${MSG:-}" python3 -c 'import json,os,datetime
print(json.dumps({"started_at":os.environ.get("START",""),"source":"notice","kind":os.environ.get("KIND",""),"prev":";"+(os.environ.get("PREV","") or ""),"pid":os.environ.get("PID",""),"class":"","evidence":os.environ.get("MSG","")[:300],"recorded_at":datetime.datetime.now().isoformat(timespec="seconds")},ensure_ascii=False))' 2>/dev/null)
if [ -n "${REC:-}" ]; then
  CLS=$(python3 -c 'import sys,json
sys.path.insert(0,"'"$W"'/tools")
mod=__import__("incident_ledger") if False else None' 2>/dev/null || true)
  python3 "$W/tools/incident-ledger.py" append "$REC" >/dev/null 2>&1 || true
fi

[ "$OK" = 0 ] && KIND="启动未就绪（$KIND）"
if [ "$KIND" = "计划内重启" ]; then
  [ -f "$W/tools/notify.sh" ] && timeout 90 bash "$W/tools/notify.sh" "$MSG" >/dev/null 2>&1 || true
else
  [ -f "$W/tools/notify.sh" ] && timeout 90 bash "$W/tools/notify.sh" --alert "$MSG" >/dev/null 2>&1 || true
fi
exit 0
