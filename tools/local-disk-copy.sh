#!/bin/bash
# 【已停用 2026-10-19 备份目录统一】SRC=/home/j/Backups 已不存在（僵尸任务），D 盘归档由主管线直发 /mnt/d/openclaw-backups；cron e1413a61 已禁用。
[ "${LOCAL_DISK_COPY_FORCE:-}" = "1" ] || { echo "local-disk-copy 已停用（2026-10-19）"; exit 0; }
# 本机第二份：全量归档同步到 D 盘（/mnt/d/openclaw-backup/archives）
set -uo pipefail
SRC=/home/j/Backups
DST=/mnt/d/openclaw-backup/archives
KEEP=14
mkdir -p "$DST" 2>/dev/null || { echo "❌ D 盘(/mnt/d)不可写，跳过"; exit 1; }
cp -f "$SRC"/*.tar.gz "$DST"/ 2>/dev/null
N=$(ls "$DST"/*.tar.gz 2>/dev/null | wc -l)
ls -t "$DST"/*.tar.gz 2>/dev/null | tail -n +$((KEEP+1)) | while read -r old; do rm -f "$old"; echo "  · 清理旧份 $(basename "$old")"; done
if [ "$N" -eq 0 ]; then echo "❌ D 盘无归档"; exit 1; fi
LATEST=$(ls -t "$DST"/*.tar.gz | head -1)
SZ=$(stat -c%s "$LATEST")
# 校验：与源一致
SRC_SZ=$(stat -c%s "$SRC/$(basename "$LATEST")" 2>/dev/null)
if [ "$SZ" = "$SRC_SZ" ]; then OK="✅ 一致"; else OK="⚠️ 大小不符(源${SRC_SZ:-?}/本机${SZ})"; fi
echo "💾 本机第二份(D盘) · $(date +%Y-%m-%dT%H:%M)"
echo "· 最新：$(basename "$LATEST")  $((SZ/1048576)) MB  $OK"
echo "· 份数：$N 份（保留 $KEEP） · 总占用：$(du -sh "$DST" 2>/dev/null | cut -f1)"
echo "· 位置：$DST（Windows D 盘，386G 可用）"
