#!/bin/bash
# nas-migrate-rest-parallel.sh —— 同一批数据并行拉取（4 路），每目录一个 tar 流
set -uo pipefail
SRC_URL=jintianyu@192.168.1.5
SRC_ROOT=/volume1/homes/jintianyu
DST=/mnt/nas/archive/jinyu/migrated-20261102
LOG=/home/j/.openclaw/workspace/state/work/nas-migrate-rest.log
LOCK=/home/j/.openclaw/workspace/state/work/nas-migrate-rest.lock
exec 9>"$LOCK"; flock -n 9 || { echo "已在跑" >&2; exit 0; }
mkdir -p "$DST"
log(){ printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }
pull(){
  local d=$1
  if ssh -q -n -o BatchMode=yes -o ConnectTimeout=15 "$SRC_URL" "tar -C $SRC_ROOT -cf - $d 2>/dev/null" | tar -C "$DST" -xf - 2>>"$LOG"; then
    log "OK $d"
  else
    log "FAIL $d"
  fi
}
EXTRA=$(ssh -q -n -o BatchMode=yes "$SRC_URL" "cd $SRC_ROOT && ls -d ws-workspace-*.git 2>/dev/null" | tr '\n' ' ')
log "=== 并行抢救开始 (max 4) ==="
N=0
for d in openclaw-backup.git openclaw-repos openclaw-backups-tier1 openclaw-backups-tier2 openclaw-trash $EXTRA; do
  [ -n "$d" ] || continue
  log "排队 $d"
  pull "$d" &
  N=$((N+1))
  if [ $((N % 4)) -eq 0 ]; then wait; fi
done
wait
log "=== 并行抢救结束 ==="
du -sh "$DST" >> "$LOG" 2>/dev/null
df -h /mnt/nas | tail -1 >> "$LOG"
bash /home/j/.openclaw/workspace/tools/notify.sh "老NAS抢救迁移完成：$(du -sh "$DST" 2>/dev/null | awk '{print $1}') 已到新NAS" >/dev/null 2>&1 || true
