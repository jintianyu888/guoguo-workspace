#!/bin/bash
# backup-tier2-medium.sh —— T2 中间数据（每周日 03:00）
# 内容：主工作区 + 22 个管家工作区（不含大媒体）
set -u
# 等空闲守卫（2026-10-02 主公令）：有其他备份/重活在跑就先等（flock 串行）
. /home/j/.openclaw/workspace/tools/backup-wait-idle.sh
. /home/j/.openclaw/workspace/tools/nas-config.sh
TS=$(date +%Y%m%d-%H%M)
W=/home/j/.openclaw/workspace
OUT=/mnt/e/openclaw-backups/tier2
LOG=$W/state/work/tier2.log
mkdir -p "$OUT"
echo "== $TS T2 中间备份 ==" >> "$LOG"
# 打包所有工作区（排除 venv/大模型/media 缓存）
cd /home/j/.openclaw

# EXCLUDE-18WORKSPACES（2026-10-02 主公令：这些已搬 E/H，只靠互备）
tar czf "$OUT/tier2-$TS.tar.gz" \
  --exclude='workspace-calendar' \
  --exclude='workspace-class-schedule' \
  --exclude='workspace-cooking' \
  --exclude='workspace-doll-brand' \
  --exclude='workspace-fitness' \
  --exclude='workspace-health-doudou' \
  --exclude='workspace-health-self' \
  --exclude='workspace-health-wife' \
  --exclude='workspace-mom-health' \
  --exclude='workspace-news' \
  --exclude='workspace-piano-app' \
  --exclude='workspace-piano-room' \
  --exclude='workspace-print' \
  --exclude='workspace-schedule-doudou' \
  --exclude='workspace-script-mystery' \
  --exclude='workspace-sheet-music' \
  --exclude='workspace-tax' \
  --exclude='workspace-wealth' \
     --exclude='*/tools/*venv*' --exclude='*/tools/models' --exclude='*media/inbound*'   --exclude='*node_modules*' --exclude='*.git'   workspace workspace-* 2>/dev/null
echo "  本地: tier2-$TS.tar.gz ($(du -h "$OUT/tier2-$TS.tar.gz" 2>/dev/null|cut -f1))" >> "$LOG"
# 推群晖 + 镜像到 E
# 推新 NAS + 镜像到 H（2026-11-02 老 NAS 断联、D 盘不再放备份）
if nas_guard "$NAS_TIER2"; then
  cp -f "$OUT/tier2-$TS.tar.gz" "$NAS_TIER2/" 2>>"$LOG" && echo "  ✅ 已推新 NAS" >> "$LOG" || echo "  ⚠️ 新 NAS 推送失败" >> "$LOG"
else
  echo "  ⚠️ 新 NAS 未挂载，跳过 tier2 推送（本地已保留）" >> "$LOG"
fi
mkdir -p /mnt/h/openclaw-backups/tier2 && cp -f "$OUT/tier2-$TS.tar.gz" /mnt/h/openclaw-backups/tier2/ 2>/dev/null && echo "  ✅ 已镜像 H" >> "$LOG" || echo "  ⚠️ H 镜像失败（cp rc=$?），需人工核对" >> "$LOG"
# 保留 8 份（约 2 个月）
ls -t "$OUT"/tier2-*.tar.gz 2>/dev/null | tail -n +9 | xargs -r rm -f
echo "  保留: $(ls "$OUT"/tier2-*.tar.gz 2>/dev/null|wc -l) 份" >> "$LOG"
