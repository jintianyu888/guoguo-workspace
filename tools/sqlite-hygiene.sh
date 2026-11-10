#!/usr/bin/env bash
# sqlite-hygiene.sh v1 —— OpenClaw SQLite 卫生（2026-11-02 事故复盘产物）
# 背景：11-02 15:27-18:08 全库 SQLITE_FULL 41 万次，根因是 lcm.db WAL 762MB 未 checkpoint
#   + 多个库共用一个 worker 池，一个库撑爆整池。
# 做法：每小时对三个库做 WAL checkpoint(TRUNCATE) + 体积监控 + 超阈值告警；每周日 vacuum。
# 安全：只做 checkpoint/vacuum，不删任何表、不改数据；busy 时跳过不重试；全程 flock 防并发。
set -u
export PATH=/home/j/.npm-global/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace
LOG=$W/state/sqlite-hygiene.log
STATE=$W/state/sqlite-hygiene.json
LOCK=$W/state/.sqlite-hygiene.lock
ALERT_BYTES=$((256*1024*1024))     # WAL 超 256MB 告警
VACUUM_BYTES=$((900*1024*1024))    # 主库超 900MB 且周日 -> vacuum
DBS="lcm.db state/openclaw.sqlite agents/main/agent/openclaw-agent.sqlite"
mkdir -p "$W/state"
log(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }

exec 9>"$LOCK"
flock -n 9 || exit 0

[ -f "$LOG" ] && [ "$(stat -c %s "$LOG")" -gt 1048576 ] && { tail -c 512K "$LOG" > "$LOG.t"; mv "$LOG.t" "$LOG"; }

cd /home/j/.openclaw || exit 0
DOW=$(date +%u)
ALERTS=""
RESULT="{"

for db in $DBS; do
  [ -f "$db" ] || continue
  wal="$db-wal"
  before=$( [ -f "$wal" ] && stat -c %s "$wal" || echo 0 )
  main=$(stat -c %s "$db")
  out=$(timeout 90 python3 - "$db" <<'PY'
import sqlite3,sys
p='/home/j/.openclaw/'+sys.argv[1]
try:
    c=sqlite3.connect(p,timeout=15)
    r=c.execute('pragma wal_checkpoint(TRUNCATE)').fetchone()
    c.close(); print('busy=%s log=%s ckpt=%s'%r)
except Exception as e:
    print('ERR',str(e)[:120])
PY
)
  after=$( [ -f "$wal" ] && stat -c %s "$wal" || echo 0 )
  log "$db main=$((main/1024/1024))MB wal=${before}->${after}B $out"
  [ "$before" -gt "$ALERT_BYTES" ] && ALERTS="$ALERTS 亚健康WAL:${db}=$((before/1024/1024))MB->$((after/1024/1024))MB"
  [ "$after" -gt "$ALERT_BYTES" ] && ALERTS="$ALERTS 严重:checkpoint未生效:${db}=$((after/1024/1024))MB"
  # 周日且主库超阈值 -> vacuum（只做一次，失败不影响其他库）
  FREE_KB=$(df -Pk /home/j/.openclaw | awk 'NR==2{print $4}')
  NEED_KB=$(( main*3/1024 ))
  FREEPG=$(timeout 20 python3 -c "
import sqlite3
c=sqlite3.connect('/home/j/.openclaw/$db',timeout=5)
f=c.execute('pragma freelist_count').fetchone()[0]; t=c.execute('pragma page_count').fetchone()[0]
print(int(f*100/t) if t else 0)" 2>/dev/null || echo 0)
  if [ "$DOW" = "7" ] && [ "$main" -gt "$VACUUM_BYTES" ] && [ "$FREEPG" -ge 25 ] && [ "$FREE_KB" -gt "$NEED_KB" ]; then
    timeout 600 python3 - "$db" <<'PY' >>"$LOG" 2>&1
import sqlite3,sys
p='/home/j/.openclaw/'+sys.argv[1]
c=sqlite3.connect(p,timeout=60)
c.execute('pragma journal_mode=wal')
c.execute('vacuum')
c.close(); print('vacuum ok',sys.argv[1])
PY
    log "$db vacuum rc=$? freelist=${FREEPG}% free=${FREE_KB}KB need=${NEED_KB}KB"
  fi
  RESULT="$RESULT\"$db\":{\"main_mb\":$((main/1024/1024)),\"wal_before\":$before,\"wal_after\":$after},"
done
RESULT="${RESULT%,}}"
printf '{"ts":"%s","dbs":%s}\n' "$(date -Iseconds)" "$RESULT" > "$STATE"

if [ -n "$ALERTS" ]; then
  log "ALERT$ALERTS"
  [ -f "$W/tools/notify.sh" ] && timeout 60 bash "$W/tools/notify.sh" --alert "SQLite 卫生告警$ALERTS" >/dev/null 2>&1 || true
fi
exit 0
