#!/bin/bash
# 重推今日归档：本地算哈希 -> 隔离 NAS 残档 -> rsync -> 远端哈希比对
set -uo pipefail
NAS=nas
NDEST=/var/services/homes/guoguonas/archive/jinyu/openclaw-archives
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/repush.log
say(){ echo "$(date '+%F %T') $*" >> "$LOG"; }
F=$(ls -t /mnt/d/openclaw-backups/*.tar.gz | head -1)
B=$(basename "$F"); S=$(stat -c%s "$F")
say "=== 开始 $B ($S 字节) ==="
H=$(sha256sum "$F" | awk '{print $1}')
echo "$H  $B" > "$F.sha256"
say "本地哈希 $H"
TS=$(date +%Y%m%d-%H%M)
ssh -o BatchMode=yes -o ConnectTimeout=15 "$NAS" "mkdir -p $NDEST/_trash/$TS; [ -f $NDEST/$B ] && mv -f $NDEST/$B $NDEST/_trash/$TS/; true" 2>/dev/null
say "旧残档已隔离到 _trash/$TS"
rsync -a --partial --inplace --timeout=300 "$F" "$NAS:$NDEST/$B" >> "$LOG" 2>&1 || { say "rsync 失败"; bash $WS/tools/notify.sh "备份重推失败" >/dev/null 2>&1; exit 1; }
rsync -a "$F.sha256" "$NAS:$NDEST/" >> "$LOG" 2>&1 || true
NH=$(ssh -o BatchMode=yes -o ConnectTimeout=15 "$NAS" "sha256sum $NDEST/$B 2>/dev/null" | awk '{print $1}')
if [ "$NH" = "$H" ]; then
  say "群晖哈希一致 $H"
  bash $WS/tools/notify.sh "今日归档已重推并校验通过：$B $S 字节" >/dev/null 2>&1 || true
else
  say "哈希不符 本地=$H 远端=${NH:-空}"
  bash $WS/tools/notify.sh "群晖哈希不符：$B" >/dev/null 2>&1 || true
  exit 1
fi
