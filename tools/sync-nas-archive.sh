#!/bin/bash
# sync-nas-archive.sh —— 把本地最新归档推群晖，并校验四地一致（D/E/H + NAS）
# 2026-10-02 主公令：D/E/H + 群晖，备份东西要一致
set -u
# 等空闲守卫（2026-10-02 主公令）：有其他备份/重活在跑就先等（flock 串行）
. /home/j/.openclaw/workspace/tools/backup-wait-idle.sh
W=/home/j/.openclaw/workspace
LOG=$W/state/work/nas-archive-sync.log
LEDGER=$W/state/backup-mirror-ledger.jsonl
NAS=nas
RDIR=/var/services/homes/guoguonas/archive/jinyu/openclaw-archives
TS=$(date '+%F %T')
echo "==== $TS 群晖归档同步 ====" >> "$LOG"

# ① 本地最新档案
LATEST=$(ls -t /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | head -1)
BN=$(basename "$LATEST")
echo "  最新本地档案: $BN ($(du -h "$LATEST"|cut -f1))" >> "$LOG"

# ② 本地已有、群晖没有的档案全部推过去
for f in /mnt/d/openclaw-backups/*.tar.gz; do
  b=$(basename "$f")
  if ssh -o ConnectTimeout=10 -o BatchMode=yes "$NAS" "test -f '$RDIR/$b'" 2>/dev/null; then
    echo "  已在群晖: $b" >> "$LOG"
  else
    echo "  推送中: $b ($(du -h "$f"|cut -f1))" >> "$LOG"
    timeout 600 scp -O -o ConnectTimeout=15 -q "$f" "$NAS:$RDIR/" >> "$LOG" 2>&1 && echo "    ✅ 推完" >> "$LOG" || echo "    ❌ 失败" >> "$LOG"
  fi
done

# ③ 四地清单对照
echo "  -- 四地档案 --" >> "$LOG"
echo "  D: $(ls /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null|wc -l)  E: $(ls /mnt/e/openclaw-backups/*.tar.gz 2>/dev/null|wc -l)  H: $(ls /mnt/h/openclaw-backups/*.tar.gz 2>/dev/null|wc -l)  NAS: $(ssh -o ConnectTimeout=10 -o BatchMode=yes "$NAS" 'ls $RDIR/*.tar.gz 2>/dev/null|wc -l' 2>/dev/null)" >> "$LOG"
printf '{"ts":"%s","d":%s,"e":%s,"h":%s,"nas":%s}\n' "$TS" "$(ls /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null|wc -l)" "$(ls /mnt/e/openclaw-backups/*.tar.gz 2>/dev/null|wc -l)" "$(ls /mnt/h/openclaw-backups/*.tar.gz 2>/dev/null|wc -l)" "$(ssh -o ConnectTimeout=10 -o BatchMode=yes "$NAS" 'ls $RDIR/*.tar.gz 2>/dev/null|wc -l' 2>/dev/null)" >> "$LEDGER"
echo "==== 结束 ====" >> "$LOG"
