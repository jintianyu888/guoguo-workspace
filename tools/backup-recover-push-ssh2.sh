#!/bin/bash
# backup-recover-push-ssh2.sh — SSH 流式推送（rsync 被 NAS 拒绝，改用 dd|ssh 追加，支持断点续传）
# 创建 2026-11-03 09:00 果果 ｜ 实测 SSH 71MB/s，CIFS 只有 5MB/s
set -uo pipefail
export PATH=/usr/local/bin:/usr/bin:/bin
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/backup-recover-20261103.log
SRC_DIR=/mnt/d/openclaw-backups
RHOST=nas
RDIR=/var/services/homes/guoguonas/archive/jinyu/openclaw-archives
SSH="ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new $RHOST"
BS=8388608   # 8M，断点按此对齐

exec >> "$LOG" 2>&1
echo "================ $(date '+%F %T') SSH 流式推送开始 ================"

F=$(ls -t "$SRC_DIR"/*.tar.gz 2>/dev/null | grep -v '\.part$' | head -1)
[ -z "$F" ] && { echo "❌ D 盘无完整包"; exit 1; }
B=$(basename "$F"); S=$(stat -c%s "$F")
echo "源: $F ($S 字节)"

$SSH "test -d $RDIR || mkdir -p $RDIR" || { echo "❌ 远端目录不可达"; exit 2; }
AV=$($SSH "df -Pk $RDIR | awk 'NR==2{print \$4*1024}'")
echo "NAS 剩余: ${AV:-0}"
[ "${AV:-0}" -lt "$((S + 1073741824))" ] && { echo "❌ NAS 空间不足"; exit 3; }

T="$RDIR/$B.part4"
RS=$($SSH "stat -c%s '$T' 2>/dev/null || echo 0")
RS=${RS:-0}
echo "[$(date '+%T')] 已存在 $((RS/1048576)) MB，从该点续传"
SKIP=$((RS / BS))
[ "$SKIP" -gt 0 ] && { $SSH "truncate -s $((SKIP * BS)) '$T'"; }

echo "[$(date '+%T')] 开始传输（8M 对齐跳过 $SKIP 块）"
dd if="$F" bs=$BS skip=$SKIP 2>/dev/null | $SSH "cat >> '$T'" || { echo "❌ 传输中断"; exit 4; }
echo "[$(date '+%T')] 传输结束"

RS=$($SSH "stat -c%s '$T' 2>/dev/null || echo 0")
echo "远端大小=$RS"
[ "$RS" = "$S" ] || { echo "❌ 大小不符 本地=$S 远端=${RS:-0}（可重跑续传）"; exit 5; }

echo "[$(date '+%T')] 源端 sha256..."
H1=$(sha256sum "$F" | awk '{print $1}')
echo "[$(date '+%T')] 远端 sha256..."
H2=$($SSH "sha256sum '$T' | awk '{print \$1}'")
echo "源=$H1"; echo "远端=$H2"
[ "$H1" = "$H2" ] || { echo "❌ sha256 不一致，保留 part4 待查"; exit 6; }

$SSH "mv -f '$T' '$RDIR/$B' && printf '%s  %s\n' '$H1' '$B' > '$RDIR/$B.sha256'" || { echo "❌ 改名失败"; exit 7; }
$SSH "rm -f '$RDIR/$B.part' '$RDIR/$B.part2' '$RDIR/$B.part3'" || true
echo "[$(date '+%T')] ✅ 已落地 NAS: $B ($S 字节, sha256=$H1)"
echo "================ $(date '+%F %T') 完成 ================"
