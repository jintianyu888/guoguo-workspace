#!/bin/bash
# after-xcopy.sh — 等分块复制结束，校验大小，再补推群晖；结果写日志+通知
set -uo pipefail
LOG=/home/j/.openclaw/workspace/state/work/x-copy-run.log
B=2026-11-25T01-02-20.250+08-00-openclaw-backup.tar.gz
SRC=/home/j/backup-stage/$B
DST=/mnt/x/openclaw-backups/$B
say(){ echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
for i in $(seq 1 240); do
  if [ -f "$DST" ]; then break; fi
  if ! systemctl --user is-active --quiet oc-xcopy2.service; then break; fi
  sleep 15
done
if [ ! -f "$DST" ]; then say "post: 复制未完成或失败"; exit 1; fi
S=$(stat -c%s "$SRC"); D=$(stat -c%s "$DST")
say "post: 大小校验 src=$S dst=$D"
[ "$S" = "$D" ] || { say "post: 大小不符"; exit 2; }
say "post: 开始推群晖"
bash /home/j/.openclaw/workspace/tools/nas-push-archive.sh >> "$LOG" 2>&1
say "post: nas-push rc=$?"
