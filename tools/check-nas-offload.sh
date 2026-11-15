#!/bin/bash
# check-nas-offload.sh —— 迁移收尾核对（一次性，2026-11-15）
cd /home/j/.openclaw/workspace
SRC=/home/j/.openclaw-archives/20261104-0846-openclaw-backup.tar.gz
DST=/mnt/nas/archive/jinyu/openclaw-archives/20261104-0846-openclaw-backup.tar.gz
LOG=state/work/nas-offload.log
ST=$(systemctl --user is-active nas-offload-1104 2>/dev/null)
if [ "$ST" = "active" ]; then
  echo "=== $(date '+%F %T') 核对：迁移仍在进行（未完成）" >> "$LOG"
  exit 0
fi
if [ -f "$SRC" ]; then
  echo "=== $(date '+%F %T') 核对：❌ 本地源仍在，迁移未成功" >> "$LOG"
  bash tools/notify.sh "归档迁移未完成" "79G 11-04 归档仍在 ext4，nas-offload 需重跑" 2>/dev/null || true
else
  if [ -f "$DST" ]; then
    echo "=== $(date '+%F %T') 核对：✅ 已迁 NAS 且本地已删 ($(stat -c %s "$DST") 字节)" >> "$LOG"
  else
    echo "=== $(date '+%F %T') 核对：⚠️ 本地已删但 NAS 无目标文件，需人工核查" >> "$LOG"
    bash tools/notify.sh "归档迁移异常" "本地已删但 NAS 找不到 20261104 归档，立即核查" 2>/dev/null || true
  fi
fi

# 2026-11-15 追加：核对今日归档 NAS 推送 + 清残片
SRC2=/mnt/d/openclaw-backups/2026-11-15T04-01-27.757+08-00-openclaw-backup.tar.gz
DST2=/mnt/nas/archive/jinyu/openclaw-archives/2026-11-15T04-01-27.757+08-00-openclaw-backup.tar.gz
if [ -f "$SRC2" ] && [ -f "$DST2" ]; then
  s1=$(stat -c %s "$SRC2"); s2=$(stat -c %s "$DST2")
  if [ "$s1" = "$s2" ]; then
    echo "=== $(date '+%F %T') 核对：✅ 今日归档已完整推到 NAS ($s2 字节)" >> "$LOG"
    for p in /mnt/nas/archive/jinyu/openclaw-archives/2026-11-15T01-02*.part /mnt/nas/archive/jinyu/openclaw-archives/2026-11-03*.part; do
      [ -f "$p" ] || continue
      sz=$(stat -c %s "$p")
      rm -f "$p" && echo "🗑  $(date '+%F %T') 清残片 $(basename "$p") ($sz 字节)" >> "$LOG"
    done
  else
    echo "=== $(date '+%F %T') 核对：⚠️ NAS 副本不完整 src=$s1 dst=$s2（推送未完成）" >> "$LOG"
  fi
else
  echo "=== $(date '+%F %T') 核对：今日归档 NAS 副本尚未生成" >> "$LOG"
fi
df -h / | tail -1 >> "$LOG"