#!/bin/bash
# oc-push-1110-verify — 等 rsync 完成，校验尺寸并推飞书（2026-11-10）
W=/home/j/.openclaw/workspace
SRC="/home/j/backup-stage/2026-11-10T01-01-55.465+08-00-openclaw-backup.tar.gz"
DST="/mnt/x/openclaw-backups/2026-11-10T01-01-55.465+08-00-openclaw-backup.tar.gz"
LOG="$W/state/backup/push-1110.log"
for i in $(seq 1 240); do
  systemctl --user is-active --quiet oc-push-1110-x || break
  sleep 30
done
s=$(stat -c %s "$SRC" 2>/dev/null || echo 0)
d=$(stat -c %s "$DST" 2>/dev/null || echo 0)
g=$((s/1024/1024/1024))
if [ "$s" = "$d" ] && [ "$s" != "0" ]; then
  msg="✅ 11-10 归档 X 副本补齐：$g G，尺寸一致（源 $s / 目标 $d）"
elif [ "$d" != "0" ]; then
  msg="⚠️ 11-10 归档 X 副本不完整：源 $s / 目标 $d"
else
  msg="⚠️ 11-10 归档 X 副本未落地：目标不存在，源 $s"
fi
echo "$(date '+%F %T') $msg" >> "$LOG"
timeout 60 sh "$W/tools/notify.sh" "$msg" >/dev/null 2>&1 || true
