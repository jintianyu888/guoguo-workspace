#!/bin/bash
# sync-cloud-backup.sh —— E:\openclaw-cloud-backup → H:\openclaw-cloud-backup（2026-10-17）
# 2026-10-17 修正：加挂载校验/单实例锁/--partial；由网关托管运行（此前被 SIGHUP 打断）
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/work/cloud-backup-sync.log
SRC=/mnt/e/openclaw-cloud-backup
DST=/mnt/h/openclaw-cloud-backup
mkdir -p "$W/state/work" || exit 1

mountpoint -q /mnt/e || { echo "== $(date '+%F %T') ABORT /mnt/e 未挂载 ==" >>"$LOG"; exit 3; }
mountpoint -q /mnt/h || { echo "== $(date '+%F %T') ABORT /mnt/h 未挂载 ==" >>"$LOG"; exit 3; }
[ -d "$SRC" ] || { echo "== $(date '+%F %T') ABORT 源目录不存在 ==" >>"$LOG"; exit 3; }

exec 9>"$W/state/work/cloud-backup-sync.lock"
flock -n 9 || { echo "== $(date '+%F %T') SKIP 已有实例在跑 ==" >>"$LOG"; exit 4; }

echo "== $(date '+%F %T') E->H cloud-backup START (pid $$) ==" >>"$LOG"
rsync -a --partial --stats \
  --exclude 'desktop.ini' --exclude '*.baiduyun.*' --exclude '.baiduyun*' --exclude '@eaDir/' \
  "$SRC/" "$DST/" >>"$LOG" 2>&1
rc=$?
E_N=$(find "$SRC" -type f 2>/dev/null | wc -l)
H_N=$(find "$DST" -type f 2>/dev/null | wc -l)
echo "== $(date '+%F %T') rc=$rc DONE  E_files=$E_N H_files=$H_N ==" >>"$LOG"
bash "$W/tools/notify.sh" "E→H 云备份同步完成：rc=$rc，E=$E_N 文件 / H=$H_N 文件" >/dev/null 2>&1
exit $rc
