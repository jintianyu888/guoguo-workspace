#!/bin/bash
# 备份状态快报：空间/时间/截至时间/异地/家底/结论
set -uo pipefail
ARCH=$(ls -dt /mnt/d/openclaw-backups /mnt/e/openclaw-backups /mnt/h/openclaw-backups /home/j/Backups 2>/dev/null | head -1); REPO=/home/j/openclaw-backup-repo; NAS=nas
SSH='ssh -o BatchMode=yes -o ConnectTimeout=15'
F='WARNING|post-quantum|vulnerable|upgraded|openssh.com'
now=$(date '+%Y-%m-%d %H:%M')
FF=$(ls -t "$ARCH"/*.tar.gz 2>/dev/null | head -1)
[ -z "$FF" ] && { echo "❌ 未找到全量归档"; exit 1; }
B=$(basename "$FF"); SZ=$(stat -c%s "$FF"); SZMB=$((SZ/1048576)); MT=$(stat -c %y "$FF" | cut -d. -f1)
AGE=$(( ($(date +%s) - $(stat -c %Y "$FF")) / 3600 ))
L=$(timeout 30 $SSH "$NAS" "stat -c%s ~/archive/jinyu/openclaw-archives/$B 2>/dev/null" 2>/dev/null | grep -vE "$F" | tr -cd 0-9)
NASTOT=$(timeout 30 $SSH "$NAS" "du -sh ~/archive/jinyu/openclaw-archives 2>/dev/null | cut -f1" 2>/dev/null | grep -vE "$F" | tr -d " \r")
LOCALC=$(ls "$ARCH"/*.tar.gz 2>/dev/null | wc -l); LOCALTOT=$(du -sh "$ARCH" 2>/dev/null | cut -f1)
L1=$(cd "$REPO" 2>/dev/null && git log -1 --format="%cd" --date=format:"%Y-%m-%d %H:%M" 2>/dev/null)
INV=$(timeout 60 $SSH "$NAS" "ls -lh --time-style=+%Y-%m-%d_%H:%M ~/archive/jinyu/openclaw-archives/*.tar.gz 2>/dev/null" 2>/dev/null | grep -vE "$F" | tr -s " " | cut -d" " -f5,6 | sort -k2 -r)
NASC=$(printf "%s\n" "$INV" | grep -c .)
echo "🗄️ 备份状态 · $now"
echo "【最新全量归档】"
echo "· 备份时间：$MT"
echo "· 截至时间：$MT（快照数据截至）"
echo "· 归档文件：$B"
echo "· 占用空间：${SZMB} MB · 距现在 ${AGE} 小时"
echo "【异地副本·群晖】"
if [ -n "$L" ] && [ "$L" = "$SZ" ]; then echo "· 推送：✅ 一致（${SZMB} MB）"; else echo "· 推送：⚠️ 不一致/缺失（本地 ${SZ} / 远端 ${L:-缺}）"; fi
echo "· 保留份数：本地 ${LOCALC} 份（${LOCALTOT}） · 群晖 ${NASC:-?} 份（${NASTOT:-?}）"
echo "【群晖备份家底（按时间 新→旧）】"
printf "%s\n" "$INV" | sed "s/^/  · /"
D2=$(ls /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | wc -l)
D2SZ=$(du -sh /mnt/d/openclaw-backups 2>/dev/null | cut -f1)
echo "【本机第二份·D盘】${D2} 份 · ${D2SZ:-?}（/mnt/d/openclaw-backups）"
echo "【近实时层·L1 数据库】最近提交 ${L1:-无} · 每 4h"
if [ -n "$L" ] && [ "$L" = "$SZ" ] && [ "${AGE:-99}" -le 30 ]; then echo "【结论】✅ 可全量恢复（DISASTER-RECOVERY.md）"; else echo "【结论】⚠️ 需检查"; fi
