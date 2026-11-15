#!/bin/bash
# nas-offload-archive.sh v1.0 —— 把 ext4 里的归档迁到 NAS，校验通过后才删本地（2026-11-15 议会 A 项）
set -u
. /home/j/.openclaw/workspace/tools/nas-config.sh
SRC=$1
[ -f "$SRC" ] || { echo "ERR 源不存在: $SRC"; exit 2; }
B=$(basename "$SRC")
DEST=$NAS_ARCHIVES/$B
LOG=/home/j/.openclaw/workspace/state/work/nas-offload.log
mkdir -p "$NAS_ARCHIVES"
SZ=$(stat -c %s "$SRC")
echo "=== $(date "+%F %T") 开始迁移 $B ($SZ 字节) -> $DEST" >> "$LOG"
need=$(( SZ / 1024 + 1048576 ))
free=$(df -Pk "$NAS_ARCHIVES" | awk "NR==2{print \$4}")
if [ "${free:-0}" -lt "$need" ]; then echo "ERR NAS 空间不足 free=${free}K need=${need}K" >> "$LOG"; exit 3; fi
sample() { local f=$1 sz m; sz=$(stat -c %s "$f"); m=$((sz/2)); { head -c 4194304 "$f"; dd if="$f" bs=1M skip=$((m/1048576)) count=4 status=none; tail -c 4194304 "$f"; } | sha256sum | cut -d" " -f1; }
echo "=== $(date "+%F %T") 复制中..." >> "$LOG"
if ! cp -f "$SRC" "$DEST.part"; then echo "ERR 复制失败" >> "$LOG"; rm -f "$DEST.part"; exit 4; fi
RSZ=$(stat -c %s "$DEST.part")
if [ "$RSZ" != "$SZ" ]; then echo "ERR 大小不符 src=$SZ dst=$RSZ" >> "$LOG"; exit 5; fi
A=$(sample "$SRC"); Bh=$(sample "$DEST.part")
if [ "$A" != "$Bh" ]; then echo "ERR 抽样哈希不符 $A vs $Bh" >> "$LOG"; exit 6; fi
mv -f "$DEST.part" "$DEST" || { echo "ERR 改名失败" >> "$LOG"; exit 7; }
echo "✅ $(date "+%F %T") 已迁到 NAS 并校验一致: $DEST ($RSZ 字节)" >> "$LOG"
rm -f "$SRC" && echo "🗑  $(date "+%F %T") 已删本地 $SRC" >> "$LOG"
df -h / | tail -1 >> "$LOG"
exit 0