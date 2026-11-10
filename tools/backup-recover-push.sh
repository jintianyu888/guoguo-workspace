#!/bin/bash
# backup-recover-push.sh — 11-03 备份链恢复第一步：把最新完整包推到 NAS 并校验
# 创建：2026-11-03 08:31 果果（主公授权动备份链）
# 只做：复制 + 校验 + 写 sha256。不删任何文件。
set -uo pipefail
export PATH=/usr/local/bin:/usr/bin:/bin
WS=/home/j/.openclaw/workspace
. "$WS/tools/nas-config.sh"
LOG=$WS/state/work/backup-recover-20261103.log
DEST="$NAS_ARCHIVES"
SRC_DIR=/mnt/d/openclaw-backups

exec >> "$LOG" 2>&1
echo "================ $(date '+%F %T') 开始：推送最新完整包 ================"

# 1. 选最新完整包（排除 .part）
F=$(ls -t "$SRC_DIR"/*.tar.gz 2>/dev/null | grep -v '\.part$' | head -1)
if [ -z "$F" ]; then echo "❌ D 盘没有完整包"; exit 1; fi
B=$(basename "$F"); S=$(stat -c%s "$F")
echo "源: $F ($S 字节)"

# 2. NAS 可用性 + 空间
nas_guard "$DEST" || { echo "❌ NAS 未挂载/写探测失败"; exit 2; }
AV=$(df -Pk "$DEST" | awk 'NR==2{print $4*1024}')
echo "NAS 剩余: $AV 字节，需要: $S 字节"
[ "${AV:-0}" -lt "$((S + 1073741824))" ] && { echo "❌ NAS 空间不足（需多留 1G 余量）"; exit 3; }

# 3. 复制到 .part2（避免与旧 .part 混淆）
T="$DEST/$B.part2"
rm -f "$T"
echo "[$(date '+%T')] 开始复制 → $T"
if ! cp -f "$F" "$T"; then echo "❌ 复制失败"; exit 4; fi
RS=$(stat -c%s "$T" 2>/dev/null)
echo "[$(date '+%T')] 复制结束，目标大小=$RS"
[ "$RS" = "$S" ] || { echo "❌ 大小不符 本地=$S 目标=$RS"; exit 5; }

# 4. 双端 sha256（流式，避免额外内存）
echo "[$(date '+%T')] 计算源端 sha256..."
H1=$(sha256sum "$F" | awk '{print $1}'); echo "源 sha256: $H1"
echo "[$(date '+%T')] 计算 NAS 端 sha256..."
H2=$(sha256sum "$T" | awk '{print $1}'); echo "NAS sha256: $H2"
[ "$H1" = "$H2" ] || { echo "❌ sha256 不一致，保留 .part2 待查"; exit 6; }

# 5. 原子改名 + 写校验文件
mv -f "$T" "$DEST/$B"
printf '%s  %s\n' "$H1" "$B" > "$DEST/$B.sha256"
echo "[$(date '+%T')] ✅ 已落地: $DEST/$B ($S 字节, sha256=$H1)"

# 6. 清理同名的旧残留 .part（同名不同扩展）
rm -f "$DEST/$B.part" && echo "已清理同名残留 .part"
echo "================ $(date '+%F %T') 完成 ================"
