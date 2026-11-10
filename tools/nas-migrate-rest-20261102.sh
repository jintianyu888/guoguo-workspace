#!/bin/bash
# nas-migrate-rest-20261102.sh —— 老 NAS 下线前抢救：OpenClaw 相关 git 仓/分级备份/回收站
# 只读源端；目标 新NAS /archive/jinyu/migrated-20261102/<同名目录>
set -uo pipefail
SRC_URL=jintianyu@192.168.1.5
SRC_ROOT=/volume1/homes/jintianyu
DST=/mnt/nas/archive/jinyu/migrated-20261102
LOG=/home/j/.openclaw/workspace/state/work/nas-migrate-rest.log
LOCK=/home/j/.openclaw/workspace/state/work/nas-migrate-rest.lock
exec 9>"$LOCK"; flock -n 9 || { echo "已在跑" >&2; exit 0; }
mkdir -p "$DST"
log(){ printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }
log "=== 抢救迁移开始 ==="
DIRS="openclaw-backup.git openclaw-repos openclaw-backups-tier1 openclaw-backups-tier2 openclaw-trash"
# ws-workspace-*.git 一并带上
EXTRA=$(ssh -q -n -o BatchMode=yes "$SRC_URL" "cd $SRC_ROOT && ls -d ws-workspace-*.git 2>/dev/null" | tr '\n' ' ')
ALL="$DIRS $EXTRA"
for d in $ALL; do
  [ -n "$d" ] || continue
  SZ=$(ssh -q -n -o BatchMode=yes "$SRC_URL" "du -sk $SRC_ROOT/$d 2>/dev/null | awk '{print \$1}'")
  log "开始 $d (${SZ:-?} KB)"
  if ssh -q -n -o BatchMode=yes "$SRC_URL" "tar -C $SRC_ROOT -cf - $d 2>/dev/null" | tar -C "$DST" -xf - 2>>"$LOG"; then
    log "OK $d"
  else
    log "FAIL $d"
  fi
done
log "=== 抢救迁移结束 ==="
du -sh "$DST" >> "$LOG" 2>/dev/null
df -h /mnt/nas | tail -1 >> "$LOG"
bash /home/j/.openclaw/workspace/tools/notify.sh "老NAS下线前抢救迁移完成：$(du -sh "$DST" 2>/dev/null | awk '{print $1}') 已到新NAS（详见 state/work/nas-migrate-rest.log）" >/dev/null 2>&1 || true
