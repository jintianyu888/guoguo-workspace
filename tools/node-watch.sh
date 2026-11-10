#!/usr/bin/env bash
# node-watch.sh v2 —— 节点探活（2026-11-02 主公："节点什么时候掉的我都不知道"）
# 背景：B 机节点 10-31 22:45 静默掉线，两天无人知晓。
# 做法：每 5 分钟查节点在线状态；状态翻转即播报；离线期间每 6 小时提醒一次；恢复时报停机时长。
# 范围：只监控「近 7 天连过」或「当前在线」的节点；更早的废弃记录标 stale 不打扰。
# 首次运行：把当前已离线且不 stale 的节点报一次现状（这正是主公要的"什么时候掉的"）。
set -u
export PATH=/home/j/.npm-global/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace
ST=$W/state/node-watch
mkdir -p "$ST"
STATE=$ST/state.json
LOG=$ST/watch.log
LOCK=$ST/.lock
REMIND=${REMIND:-21600}     # 6 小时
log(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }

exec 9>"$LOCK"
flock -n 9 || exit 0
[ -f "$LOG" ] && [ "$(stat -c %s "$LOG")" -gt 524288 ] && { tail -c 256K "$LOG" > "$LOG.t"; mv "$LOG.t" "$LOG"; }

JSON=$(timeout 45 openclaw nodes list --json 2>/dev/null)
if [ -z "$JSON" ]; then log "nodes list 无输出，跳过本轮"; exit 0; fi

python3 - "$STATE" "$(date +%s)" "$REMIND" "$JSON" <<'PY' > "$ST/.msgs"
import json,sys,time
state_path,now,remind,raw = sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),sys.argv[4]
try: data=json.loads(raw)
except Exception: sys.exit(0)
nodes=data.get('paired') or data.get('nodes') or []
if not nodes:
    sys.stderr.write('empty node list, keep previous state\n'); sys.exit(0)
try: prev=json.load(open(state_path))
except Exception: prev={}
out={}; WINDOW=7*86400
def ts(t): return time.strftime('%m-%d %H:%M',time.localtime(t)) if t else '未知'
for n in nodes:
    nid=n.get('nodeId') or ''
    if not nid: continue
    name=n.get('displayName') or nid[:8]
    conn=bool(n.get('connected'))
    last=(n.get('lastConnectedAtMs') or 0)/1000.0
    stale=(not conn) and ((now-last) > WINDOW)
    p=prev.get(nid,{})
    was=p.get('connected')
    if conn:
        if was is False and not stale:
            down=now-int(p.get('since',now))
            print("ok\t【节点恢复】%s\n停机 %d小时%d分（自 %s）\n网关可再次调度该节点。"%(name,down//3600,down%3600//60,ts(p.get('since'))))
        out[nid]={'connected':True,'since':int(p.get('since',now)) if was else now,'last_alert':0,'last_seen':now}
    else:
        since=int(p.get('since', last or now))
        lastalert=int(p.get('last_alert',0))
        first=(was is None)
        # 首次见到且已离线：报一次现状（这是"什么时候掉的"的答案），但 stale 的旧记录不报
        if first and not stale:
            print("alert\t【节点离线】%s\n最后一次连接：%s（约 %d 小时前）\n现在连不上，需要时我把拉起命令发你。"%(name,ts(last),(now-last)//3600 if last else 0))
            lastalert=now
        elif (not first) and (not stale) and (now-lastalert>remind):
            lastalert=now
            down=now-since
            print("alert\t【节点仍离线】%s\n已离线 %d小时%d分"%(name,down//3600,down%3600//60))
        out[nid]={'connected':False,'since':since,'last_alert':lastalert,'last_seen':int(last) if last else int(p.get('last_seen',now))}
json.dump(out,open(state_path,'w'))
PY

[ -s "$ST/.msgs" ] || exit 0
while IFS=$'\t' read -r kind msg; do
  [ -z "$msg" ] && continue
  MSG=$(printf '%b' "$msg")
  log "SEND[$kind] $(echo "$MSG" | head -1)"
  if [ "$kind" = "alert" ] || echo "$MSG" | grep -q '【节点恢复】'; then
    timeout 90 bash "$W/tools/notify.sh" --alert "$MSG" >/dev/null 2>&1 || { log "notify 失败(alert)"; echo "[$(date '+%F %T')] NOTIFY-FAIL $kind $MSG" >> "$ST/failed.log"; }
  else
    timeout 90 bash "$W/tools/notify.sh" "$MSG" >/dev/null 2>&1 || { log "notify 失败(info)"; echo "[$(date '+%F %T')] NOTIFY-FAIL $kind $MSG" >> "$ST/failed.log"; }
  fi
done < "$ST/.msgs"
exit 0
