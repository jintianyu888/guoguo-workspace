#!/usr/bin/env bash
# gateway-watchdog.sh v3 —— 网关掉线兜底（2026-10-25 主公令：重启=高危）
# v3 按双审必改项：HTTP /health 真存活判据（ss LISTEN 抓不到假死）、reset-failed、flock、陈旧标志清理
set -u
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace
STATE=$W/state/work/gateway-watchdog.state
LOG=$W/state/work/gateway-watchdog.log
LOCK=$W/state/work/.gateway-ctl.lock
FLAG=$W/state/work/.safe-restart-running
PORT=18789
PAT="dist/index.js gateway"
WINDOW=1800
MAXTRY=3
log(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }
[ -f "$LOG" ] && [ $(stat -c %s "$LOG" 2>/dev/null || echo 0) -gt 1048576 ] && tail -c 512K "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"

# 2026-11-07 21:47：维护标记过期后自动清理，避免 .watchdog-pause 残留把看门狗永久停掉
if [ -f "$W/state/work/.maintenance" ]; then
  _mu=$(awk '{print $1}' "$W/state/work/.maintenance" 2>/dev/null)
  if [ -n "${_mu:-}" ] && [ "$(date +%s)" -ge "${_mu:-0}" ]; then
    rm -f "$W/state/work/.maintenance" "$W/state/work/.watchdog-pause"
    log "维护标记已过期，自动清理（恢复看门狗）"
  fi
fi
[ -f "$W/state/work/.watchdog-pause" ] && exit 0

pid_of(){ pgrep -f "$PAT" | head -1; }
http_ok(){ [ "$(timeout 15 curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health" 2>/dev/null)" = "200" ]; }
http_ok2(){ http_ok || { sleep 45; http_ok; }; }   # 双发探针：15s 超时 + 45s 复探（实测 eventLoopDelay P99=54s，20s 复探会假阳性误重启）
# 2026-11-02 加：真写探测。当天 15:27-18:08 出现「/health 200 但全库 SQLITE_FULL」的假活，
# 2h41m 内 41 万次写失败；看门狗按 /health 判活，因此完全失明，只能靠主公跑 doctor 救。
# 现在必须能真写一条才算活。locked/busy 属瞬时争用，不算死。
db_ok(){
  timeout 20 python3 -c '
import sqlite3, sys
bad = ("full", "readonly", "read-only", "corrupt", "i/o", "malformed", "disk")
paths = ["/home/j/.openclaw/state/openclaw.sqlite",
         "/home/j/.openclaw/agents/main/agent/openclaw-agent.sqlite"]
for p in paths:
    try:
        c = sqlite3.connect(p, timeout=8)
        c.execute("create table if not exists __wd_probe(x integer)")
        c.execute("insert into __wd_probe values(1)")
        c.commit()
        c.execute("delete from __wd_probe")
        c.commit()
        c.close()
    except Exception as e:
        m = str(e).lower()
        if any(b in m for b in bad):
            sys.exit(1)
print("ok")
' >/dev/null 2>&1
}
alive(){ [ -n "$(pid_of)" ] && http_ok2 && db_ok; }

# 陈旧标志：SIGKILL 残留会让看门狗永久失明
if [ -f "$FLAG" ]; then
  AGE=$(( $(date +%s) - $(stat -c %Y "$FLAG" 2>/dev/null || echo 0) ))
  [ "$AGE" -gt 600 ] && { log "陈旧 .safe-restart-running($AGE s)，清理"; rm -f "$FLAG"; }
fi

BOOTID=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo unknown)
UMGEN=$(ps -o ppid= -p $$ 2>/dev/null | tr -d " "); UMGEN=${UMGEN:-unknown}   # systemd user manager 代际（本轮事故是 manager 反复重启，boot_id 未变）
if alive; then
  # 健康即清零（v4 修 kimi 复盘 bug：原来健康时不复位，假阳性烧光预算）
  [ -s "$STATE" ] && echo "$(date +%s) 0 $BOOTID 0 0 $UMGEN" > "$STATE"
  exit 0
fi

exec 9>"$LOCK"
flock -n 9 || exit 0
[ -f "$FLAG" ] && exit 0

# 消费安全重启脚本的退出码（v4-pro 评审：看门狗不能只看端口）
PREVFAIL=0; PREVRC=""; PREVAGE=0
RC_FILE=$W/state/work/safe-restart-result.json.rc
if [ -s "$RC_FILE" ]; then
  PREVRC=$(cat "$RC_FILE" 2>/dev/null | tr -d '[:space:]')
  MT=$(stat -c %Y "$W/state/work/safe-restart-result.json" 2>/dev/null || echo 0)
  PREVAGE=$(( $(date +%s) - MT ))
  if [ "$PREVRC" != "0" ] && [ "$PREVAGE" -lt 900 ]; then
    PREVFAIL=1
    log "上一次安全重启 rc=$PREVRC（${PREVAGE}秒前），本轮带上下文处理"
  fi
fi

NOW=$(date +%s)
TRY=0; FIRST=0; OLD_BOOT=""; ALARMED=0; FAILSEQ=0; OLD_GEN=""
[ -s "$STATE" ] && { read -r FIRST TRY OLD_BOOT ALARMED FAILSEQ OLD_GEN < "$STATE" 2>/dev/null || { FIRST=0; TRY=0; OLD_BOOT=""; ALARMED=0; FAILSEQ=0; OLD_GEN=""; }; }
if [ "${OLD_BOOT:-}" != "$BOOTID" ] || [ "${OLD_GEN:-}" != "$UMGEN" ]; then
  log "环境代际变化(boot ${OLD_BOOT:-none}→$BOOTID, manager ${OLD_GEN:-none}→$UMGEN) → 仅复位失败序列；TRY/ALARMED 跨代际保留（防重启风暴自我解除熔断，2026-10-26 双审必改）"
  FAILSEQ=0
fi
[ "${FIRST:-0}" -eq 0 ] 2>/dev/null && FIRST=$NOW
[ $(( NOW - FIRST )) -gt $WINDOW ] && { FIRST=$NOW; TRY=0; ALARMED=0; }
# v4.1（v4-pro 评审必改）：单周期双发探针在事件循环卡死 54s 时仍可能同时失败，
# 故再要求连续两个看门狗周期都失败才动手，避免单次抖动误重启。
FAILSEQ=$((FAILSEQ+1))
if [ "$FAILSEQ" -lt 2 ]; then
  log "本轮判失败(第 $FAILSEQ/2 次)，不重启，等下一轮确认（检出最差延迟约 4-6 分钟）"
  echo "$FIRST $TRY $BOOTID 0 $FAILSEQ $UMGEN" > "$STATE"
  exit 0
fi
log "异常: pid=$(pid_of) http=$(http_ok && echo 200 || echo down) 第 $((TRY+1))/$MAXTRY 次"
echo "$FIRST $((TRY+1)) $BOOTID 0 $FAILSEQ $UMGEN" > "$STATE"
if [ "$TRY" -ge "$MAXTRY" ]; then
  if [ "${ALARMED:-0}" = "1" ]; then log "达上限（本窗口已告警过，静默）"; exit 3; fi
  log "达上限，停手告警"
  echo "$FIRST $TRY $BOOTID 1 $FAILSEQ $UMGEN" > "$STATE"
  timeout 60 bash "$W/tools/notify.sh" --alert "GATEWAY-DOWN: watchdog $MAXTRY attempts/30min still down; last safe-restart rc=${PREVRC:-none} (${PREVAGE}s ago); manual fix needed. log $LOG" >/dev/null 2>&1 || true
  exit 3
fi
# 上一次安全重启已失败 -> 先做一次 doctor 自修复（网关进程外执行）
if [ "$PREVFAIL" = "1" ] && [ "$TRY" -ge 1 ]; then
  log "前次重启失败(rc=$PREVRC) 且这是第 $((TRY+1)) 次拉起，先跑 doctor --fix"
  timeout 600 openclaw doctor --fix >>"$LOG" 2>&1 || true
fi
# 拉起前先确认 systemd user 实例可用（v4.2）：实例垂死时 start 只会连吃 exit-1 并烧预算
SR=$(systemctl --user is-system-running 2>/dev/null || true)
case "$SR" in
  running|degraded) ;;
  *) log "systemd user 实例不可用(state=${SR:-none})，本轮不拉起，交人工/自救程序"; exit 0;;
esac
systemctl --user reset-failed openclaw-gateway 2>/dev/null || true
timeout 200 systemctl --user start openclaw-gateway >>"$LOG" 2>&1 || true
sleep 20
if alive; then
  log "拉起成功"
  echo "$(date +%s) 0 $BOOTID 0 0 $UMGEN" > "$STATE"
  timeout 40 bash "$W/tools/notify.sh" "GATEWAY-AUTO-RECOVERED: watchdog started gateway" >/dev/null 2>&1 || true
  exit 0
fi
log "本次未成功，等下一轮"
exit 2
