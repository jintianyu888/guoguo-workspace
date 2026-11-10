#!/bin/bash
# 百度网盘暂存区刷新：把存储区/工作区以硬链接方式铺成真实文件（不占额外空间）
set -u
CLOUD=/mnt/e/openclaw-cloud-backup
LOG=/home/j/.openclaw/workspace/state/cloud-stage.log
stage(){ SRC=$1; DST=$2; [ -d "$SRC" ] || { echo "$(date "+%F %T") skip $DST (无源)" >>"$LOG"; return; }; rm -rf "$DST"; mkdir -p "$DST"; cp -al "$SRC/." "$DST/" 2>>"$LOG"; S=$(find "$SRC" -type f | wc -l); D=$(find "$DST" -type f | wc -l); echo "$(date "+%F %T") $DST 文件 $D/$S" >>"$LOG"; }
stage /mnt/e/openclaw-store/scores "$CLOUD/乐谱库"
stage /mnt/e/openclaw-store/cooking-videos "$CLOUD/做菜视频"
stage /mnt/e/openclaw-store/script-mystery-media "$CLOUD/剧本素材"
# 2026-10-17 主公令：健康管家仓库不进云备份（隐私）。用 rsync 硬链接并显式排除。
stage_ws(){ SRC=/home/j/openclaw-workspaces; DST="$CLOUD/管家工作区"; [ -d "$SRC" ] || { echo "$(date "+%F %T") skip $DST (无源)" >>"$LOG"; return; }
  rm -rf "$DST"; mkdir -p "$DST"
  rsync -a --link-dest="$SRC" --exclude mom-health --exclude health-doudou --exclude health-self --exclude health-wife --exclude fitness "$SRC/" "$DST/" 2>>"$LOG"
  S=$(find "$SRC" -type f -not -path "*/mom-health/*" -not -path "*/health-*/*" | wc -l); D=$(find "$DST" -type f | wc -l)
  echo "$(date "+%F %T") $DST 文件 $D/$S (健康管家已排除)" >>"$LOG"; }
stage_ws
exit 0