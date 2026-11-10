#!/bin/bash
# backup-local.sh —— 例外/临时备份：只打包 + 只落 D 盘，不推 NAS、不做 E/H 镜像
# 2026-11-05 主公令：临时的备份先落一份，等升级完再统一推送 E/H/群晖，省时间
set -u
export OC_SQLITE_PROBE_TIMEOUT_MS="${OC_SQLITE_PROBE_TIMEOUT_MS:-180000}"
WS=/home/j/.openclaw/workspace
STAGE=/home/j/backup-stage
OUT=/mnt/d/openclaw-backups
LOG=$WS/state/work/bk-run.log
PENDING=$WS/state/work/pending-backup-push
mkdir -p "$OUT" "$STAGE" || exit 1

echo "=== $(date '+%F %T') 本地备份开始（不推送） ===" >> "$LOG"
sh "$WS/tools/stage-agent-dbs.sh" >> "$LOG" 2>&1
sh "$WS/tools/gen-recovery-doc.sh" >> "$LOG" 2>&1
sh "$WS/tools/backup-report.sh" > "$WS/state/backup-report.txt" 2>&1
echo "=== $(date '+%F %T') 开始在原生盘打包 ===" >> "$LOG"
# 2026-11-06 告警修复：sqlite 头探测 10s 硬超时，慢盘/冷缓存下会误杀整次备份 → 有界重试 3 次
BAK_OK=0
for i in 1 2 3; do
  TRY="$STAGE/.try$i"; rm -rf "$TRY"; mkdir -p "$TRY"
  echo "=== $(date '+%F %T') openclaw backup 尝试 $i/3 ===" >> "$LOG"
  if openclaw backup create --output "$TRY" --verify >> "$LOG" 2>&1; then
    mv -f "$TRY"/*.tar.gz "$STAGE"/ 2>/dev/null
    rm -rf "$TRY"; BAK_OK=1; break
  fi
  echo "=== $(date '+%F %T') 尝试 $i 失败，清理后重试 ===" >> "$LOG"
  rm -rf "$TRY"; sleep 20
done
if [ "$BAK_OK" != "1" ]; then
  echo "=== $(date '+%F %T') 打包连续 3 次失败 ===" >> "$LOG"
  exit 1
fi
F=$(ls -t "$STAGE"/*.tar.gz 2>/dev/null | head -1)
if [ -z "$F" ]; then echo "=== $(date '+%F %T') 未找到归档 ===" >> "$LOG"; exit 1; fi
B=$(basename "$F"); S=$(stat -c%s "$F")
echo "=== $(date '+%F %T') 打包完成 $B ($S 字节)，先落 X 盘 ===" >> "$LOG"
mkdir -p /mnt/x/openclaw-backups
if cp -f "$F" "/mnt/x/openclaw-backups/$B.part" && mv -f "/mnt/x/openclaw-backups/$B.part" "/mnt/x/openclaw-backups/$B"; then
  XS=$(stat -c%s "/mnt/x/openclaw-backups/$B" 2>/dev/null || echo 0)
  if [ "$XS" != "$S" ]; then echo "=== X 盘大小不符 $XS != $S ===" >> "$LOG"; exit 1; fi
  echo "✅ 第一份已落 X 盘: $B" >> "$LOG"
else echo "=== 复制到 X 失败 ===" >> "$LOG"; exit 1; fi
echo "=== $(date '+%F %T') 再落 D 盘 ===" >> "$LOG"
if cp -f "$F" "$OUT/$B.part" && mv -f "$OUT/$B.part" "$OUT/$B"; then
  DS=$(stat -c%s "$OUT/$B" 2>/dev/null || echo 0)
  if [ "$DS" != "$S" ]; then echo "=== 复制到 D 后大小不符 本地=$S D=$DS ===" >> "$LOG"; exit 1; fi
  echo "✅ 已落 D 盘: $B ($DS 字节)，未推送（等升级后统一推）" >> "$LOG"
else
  echo "=== 复制到 D 失败 ===" >> "$LOG"; exit 1
fi
echo "$B" > "$PENDING"
echo "=== $(date '+%F %T') 完成（本地）rc=0，待推送标记已写 ===" >> "$LOG"
rm -f "$F"
exit 0
