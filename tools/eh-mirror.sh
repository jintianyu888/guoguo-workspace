#!/bin/bash
# eh-mirror.sh —— E/H 盘互备（2026-10-02 主公令：不重要仓库只需 E/H 相互备份）
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/work/eh-mirror.log
echo "== $(date '+%F %T') E<->H 互备 ==" >> "$LOG"
# E -> H（源 E 为准，增量为补）
rsync -a --delete --info=none --exclude sheet-music/scores --exclude cooking/videos --exclude script-mystery/media --exclude mom-health --exclude health-doudou --exclude health-self --exclude health-wife --exclude fitness /home/j/openclaw-workspaces/ /mnt/h/openclaw-workspaces/ >>"$LOG" 2>&1
# 2026-10-17 主公令：健康/运动管家仓库放在百度云盘目录，参与 E/H 互备
rsync -a --delete --info=none --exclude "*.baiduyun.*" /mnt/e/openclaw-cloud-backup/健康管家工作区/ /mnt/h/openclaw-cloud-backup/健康管家工作区/ >>"$LOG" 2>&1 && echo '  ✅ 健康管家目录 E→H 完成' >> "$LOG" || echo '  ❌ 健康管家目录 E→H 失败' >> "$LOG" && echo '  ✅ E→H 完成' >> "$LOG" || echo '  ❌ E→H 失败' >> "$LOG"
# 2026-10-17 主公令：cloud-backup 目录 E→H 同步（百度云暂存区，排除百度临时文件）
rsync -a --delete --exclude 'desktop.ini' --exclude '*.baiduyun.*' --exclude '.baiduyun*' /mnt/e/openclaw-cloud-backup/ /mnt/h/openclaw-cloud-backup/ >>"$LOG" 2>&1 && echo '  ✅ cloud-backup E→H 完成' >> "$LOG" || echo '  ❌ cloud-backup E→H 失败' >> "$LOG"
# 汇总
for d in e h; do echo -n "  $d: " >> "$LOG"; du -sh /mnt/$d/openclaw-workspaces 2>/dev/null | cut -f1 >> "$LOG"; done
ls -1 /home/j/openclaw-workspaces 2>/dev/null | tr '\n' ' ' >> "$LOG"; echo >> "$LOG"