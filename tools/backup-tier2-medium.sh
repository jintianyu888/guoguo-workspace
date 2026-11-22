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
mkdir -p /mnt/h/openclaw-backups/tier2
# 2026-11-22 改为后台 systemd + rsync（9p 上 cp 37G 必挂，rc=1）
if systemd-run --user --collect --no-block --unit="tier2-e2h-$(date +%Y%m%d-%H%M)" \
    nice -n 10 ionice -c2 -n7 rsync -a --partial --inplace "$OUT/tier2-$TS.tar.gz" /mnt/h/openclaw-backups/tier2/ >/dev/null 2>&1; then
  echo "  ✅ H 镜像已交后台单元" >> "$LOG"
else
  echo "  ⚠️ H 镜像后台单元启动失败" >> "$LOG"
fi
# 保留 4 份（2026-11-22：E 盘瘦身，约 1 个月）
ls -t "$OUT"/tier2-*.tar.gz 2>/dev/null | tail -n +5 | xargs -r rm -f
echo "  保留: $(ls "$OUT"/tier2-*.tar.gz 2>/dev/null|wc -l) 份" >> "$LOG"
