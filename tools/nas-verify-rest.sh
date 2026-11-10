#!/bin/bash
# nas-verify-rest.sh —— 对 6 份无清单可比的归档做远端 SHA256 复核（只读取源端，不改任何文件）
set -uo pipefail
SRC_HOST=jintianyu@192.168.1.5
SRC_DIR=/volume1/homes/jintianyu/openclaw-archives
DST=/mnt/nas/archive/jinyu/openclaw-archives
LOG=/home/j/.openclaw/workspace/state/work/nas-verify-rest.log
FILES="2026-10-21T13-01-12.822+08-00-openclaw-backup.tar.gz 2026-10-22T01-01-12.644+08-00-openclaw-backup.tar.gz 2026-10-23T01-01-12.533+08-00-openclaw-backup.tar.gz 2026-10-23T13-01-22.430+08-00-openclaw-backup.tar.gz 2026-10-25T01-01-14.606+08-00-openclaw-backup.tar.gz 2026-10-27T01-01-54.590+08-00-openclaw-backup.tar.gz"
log(){ printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }
log "=== 复核开始 ==="
OK=0; BAD=0
for f in $FILES; do
  SH=$(ssh -q -n -o BatchMode=yes -o ConnectTimeout=15 "$SRC_HOST" "sha256sum '$SRC_DIR/$f'" 2>/dev/null | awk '{print $1}')
  LH=$(awk '{print $1}' "$DST/$f.sha256" 2>/dev/null)
  if [ -n "$SH" ] && [ "$SH" = "$LH" ]; then log "✓ $f $SH"; OK=$((OK+1)); else log "✗ $f src=${SH:-空} dst=${LH:-空}"; BAD=$((BAD+1)); fi
done
log "=== 复核结束 ok=$OK bad=$BAD ==="
bash /home/j/.openclaw/workspace/tools/notify.sh "NAS归档迁移复核：一致 $OK 份，不一致 $BAD 份（详见 state/work/nas-verify-rest.log）" >/dev/null 2>&1 || true
