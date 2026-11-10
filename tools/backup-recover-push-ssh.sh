#!/bin/bash
# backup-recover-push-ssh.sh — 走 SSH 推最新完整包到新 NAS（CIFS 只有 5MB/s，SSH 实测 71MB/s）
# 创建 2026-11-03 08:50 果果 ｜ 紧急：11-03 尚无完整包落 NAS
# 只做：rsync 推 + 双端 sha256 + 改名 + 写校验文件。不删任何归档。
set -uo pipefail
export PATH=/usr/local/bin:/usr/bin:/bin
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/backup-recover-20261103.log
SRC_DIR=/mnt/d/openclaw-backups
RHOST=guoguonas@192.168.1.109
RPORT=2222
RKEY=/home/j/.ssh/nas_guoguo
RDIR=/var/services/homes/guoguonas/archive/jinyu/openclaw-archives
SSHOPTS="-o BatchMode=yes -o StrictHostKeyChecking=accept-new -p $RPORT -i $RKEY"

exec >> "$LOG" 2>&1
echo "================ $(date '+%F %T') SSH 推送开始 ================"

F=$(ls -t "$SRC_DIR"/*.tar.gz 2>/dev/null | grep -v '\.part$' | head -1)
[ -z "$F" ] && { echo "❌ D 盘无完整包"; exit 1; }
B=$(basename "$F"); S=$(stat -c%s "$F")
echo "源: $F ($S 字节)"

ssh $SSHOPTS "$RHOST" "test -d $RDIR || mkdir -p $RDIR" || { echo "❌ 远端目录不可达"; exit 2; }
AV=$(ssh $SSHOPTS "$RHOST" "df -Pk $RDIR | awk 'NR==2{print \$4*1024}'")
echo "NAS 剩余: ${AV:-0} 字节"
[ "${AV:-0}" -lt "$((S + 1073741824))" ] && { echo "❌ NAS 空间不足"; exit 3; }

T="$RDIR/$B.part3"
echo "[$(date '+%T')] rsync 开始 → $T"
rsync -a --partial --inplace --append-verify \
  -e "ssh $SSHOPTS" "$F" "$RHOST:$T" || { echo "❌ rsync 失败"; exit 4; }
echo "[$(date '+%T')] rsync 结束"

RS=$(ssh $SSHOPTS "$RHOST" "stat -c%s '$T' 2>/dev/null")
echo "远端大小=$RS"
[ "$RS" = "$S" ] || { echo "❌ 大小不符 本地=$S 远端=${RS:-0}"; exit 5; }

echo "[$(date '+%T')] 源端 sha256..."
H1=$(sha256sum "$F" | awk '{print $1}')
echo "[$(date '+%T')] 远端 sha256（NAS 自算）..."
H2=$(ssh $SSHOPTS "$RHOST" "sha256sum '$T' | awk '{print \$1}'")
echo "源=$H1"; echo "远端=$H2"
[ "$H1" = "$H2" ] || { echo "❌ sha256 不一致，保留 part3 待查"; exit 6; }

ssh $SSHOPTS "$RHOST" "mv -f '$T' '$RDIR/$B' && printf '%s  %s\n' '$H1' '$B' > '$RDIR/$B.sha256'" || { echo "❌ 改名/写校验失败"; exit 7; }
# 清同类残片
ssh $SSHOPTS "$RHOST" "rm -f '$RDIR/$B.part' '$RDIR/$B.part2'" || true
echo "[$(date '+%T')] ✅ 已落地 NAS: $B ($S 字节, sha256=$H1)"
echo "================ $(date '+%F %T') 完成 ================"
