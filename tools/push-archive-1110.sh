#!/bin/bash
# push-archive-1110.sh — 把 11-10 全量包补推到 D/E/H/NAS（2026-11-10）
W=/home/j/.openclaw/workspace
SRC=/home/j/backup-stage/2026-11-10T01-01-55.465+08-00-openclaw-backup.tar.gz
NAME=$(basename "$SRC")
LOG=$W/state/backup/push-1110.log
S=$(stat -c %s "$SRC")
ok=0; fail=0; msg=""
for dst in /mnt/d/openclaw-backups /mnt/e/openclaw-backups /mnt/h/openclaw-backups /mnt/nas/archive/jinyu/openclaw-archives; do
  [ -d "$dst" ] || { msg="$msg$dst(缺目录) "; fail=$((fail+1)); continue; }
  D=$(stat -c %s "$dst/$NAME" 2>/dev/null || echo 0)
  if [ "$D" != "$S" ]; then
    /usr/bin/rsync -a --partial --inplace "$SRC" "$dst/" >>"$LOG" 2>&1
    D=$(stat -c %s "$dst/$NAME" 2>/dev/null || echo 0)
  fi
  if [ "$D" = "$S" ]; then ok=$((ok+1)); msg="$msg$(basename $(dirname $dst))✓ "; else fail=$((fail+1)); msg="$msg$(basename $(dirname $dst))✗$(($D/1024/1024))MB "; fi
done
echo "$(date '+%F %T') 补推结果 ok=$ok fail=$fail $msg" >> "$LOG"
if [ $fail -eq 0 ]; then R="✅ 11-10 归档已补齐 4 处（D/E/H/NAS），尺寸一致 117.1G"; else R="⚠️ 11-10 归档补推：成功 $ok 处，失败 $fail 处（$msg）"; fi
timeout 60 sh "$W/tools/notify.sh" "$R" >/dev/null 2>&1 || true