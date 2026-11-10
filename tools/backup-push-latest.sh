#!/bin/bash
# backup-push-latest.sh —— 把 D 盘最新归档推到群晖 + 镜像 E/H，成功后清待推送标记
set -u
W=/home/j/.openclaw/workspace
OUT=/mnt/d/openclaw-backups
LOG=$W/state/work/bk-run.log
PENDING=$W/state/work/pending-backup-push
. "$W/tools/nas-config.sh"
DEST="$NAS_ARCHIVES"

if [ -n "${1:-}" ]; then B="$1"; else
  if [ -f "$PENDING" ]; then B=$(cat "$PENDING"); else B=$(ls -t "$OUT"/*.tar.gz 2>/dev/null | head -1 | xargs -r basename); fi
fi
[ -z "${B:-}" ] && { echo "=== $(date "+%F %T") 推送失败：没有可推的归档 ===" >> "$LOG"; exit 1; }
SRC="$OUT/$B"
[ -f "$SRC" ] || { echo "=== $(date "+%F %T") 推送失败：$SRC 不存在 ===" >> "$LOG"; exit 1; }
S=$(stat -c%s "$SRC")
echo "=== $(date "+%F %T") 开始推送 $B ($S 字节) ===" >> "$LOG"
RC=0
if nas_guard "$DEST"; then
  AV=$(df -Pk "$DEST" | awk "NR==2{print $4*1024}")
  if [ "${AV:-0}" -lt "$S" ]; then
    echo "❌ 群晖空间不足：剩余 ${AV:-0}，需要 $S —— 跳过" >> "$LOG"; RC=1
  else
    if cp -f "$SRC" "$DEST/$B.part" && mv -f "$DEST/$B.part" "$DEST/$B"; then
      R=$(stat -c%s "$DEST/$B" 2>/dev/null || echo 0)
      if [ "$R" = "$S" ]; then echo "✅ 群晖: $B ($R)" >> "$LOG"; else echo "❌ 群晖大小不符 本地=$S 远端=$R" >> "$LOG"; RC=1; fi
    else
      echo "❌ 群晖复制失败" >> "$LOG"; RC=1
    fi
  fi
else
  echo "⚠️ 群晖未挂载：跳过推送，本地归档保留" >> "$LOG"
fi
echo "=== $(date "+%F %T") 开始 E/H 镜像+校验 ===" >> "$LOG"
if bash "$W/tools/backup-mirror-verify.sh" >> "$LOG" 2>&1; then
  echo "✅ E/H 镜像与校验完成" >> "$LOG"
else
  echo "❌ E/H 镜像或校验失败，见 mirror-verify.log" >> "$LOG"; RC=1
fi
if [ "$RC" = "0" ]; then
  rm -f "$PENDING"
  echo "=== $(date "+%F %T") 推送完成 rc=0 ===" >> "$LOG"
else
  echo "=== $(date "+%F %T") 推送未全成功 rc=$RC（待推送标记保留） ===" >> "$LOG"
fi
exit "$RC"
