#!/bin/bash
# rsync 在本群晖不可用(协议栈失败) -> 哈希校验流式推送
set -uo pipefail
NAS=nas
NDEST=/var/services/homes/guoguonas/archive/jinyu/openclaw-archives
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/push-stream.log
say(){ echo "$(date '+%F %T') $*" >> "$LOG"; }
F=$(ls -t /mnt/d/openclaw-backups/*.tar.gz | head -1)
B=$(basename "$F"); S=$(stat -c%s "$F")
H=$(sha256sum "$F" | awk '{print $1}')
say "=== 流式推送开始 $B $S 字节 哈希 $H ==="
echo "$H  $B" > "$F.sha256"
cat "$F" | ssh -o BatchMode=yes -o ConnectTimeout=15 "$NAS" "cat > $NDEST/$B.part" || { say "推送失败"; exit 1; }
say "传输结束，校验远端哈希"
NH=$(ssh -o BatchMode=yes "$NAS" "sha256sum $NDEST/$B.part" 2>/dev/null | awk '{print $1}')
if [ "$NH" = "$H" ]; then
  ssh -o BatchMode=yes "$NAS" "mv -f $NDEST/$B.part $NDEST/$B" && say "校验一致，已落位"
  scp -q -o BatchMode=yes "$F.sha256" "nas:$NDEST/" 2>/dev/null || true
  bash $WS/tools/notify.sh "今日归档已推送并哈希校验通过：$B" >/dev/null 2>&1 || true
else
  say "哈希不符 本地=$H 远端=${NH:-空}，.part 保留待查"
  bash $WS/tools/notify.sh "群晖哈希不符：$B，已冻结" >/dev/null 2>&1 || true
  exit 1
fi
