#!/usr/bin/env bash
# pack-check-upgrade.sh —— 新备份 → 清空间 → 全面体检 → 体检绿才升级（2026-11-21 主公令）
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/work/pack-check-upgrade.log
exec >>"$LOG" 2>&1
echo "=== $(date "+%F %T") 开始：强制新打包备份"

# 1) 新备份（FORCE_PACK 绕过"今日已有归档"去重）
FORCE_PACK=1 bash "$W/tools/backup-run.sh"
BRC=$?
echo "=== $(date "+%F %T") 备份结束 rc=$BRC"
[ $BRC -ne 0 ] && { echo "备份失败，不升级"; exit 3; }

# 2) 清出 E 盘空间：已知坏件的半截文件（事故残留），不做泛删
shopt -s nullglob
for f in /mnt/e/openclaw-backups/_trash/ubuntu-*.tar.part /mnt/e/openclaw-backups/_trash/tier2-partial-*.tar.gz; do
  [ -e "$f" ] || continue
  sz=$(stat -c %s "$f" 2>/dev/null || echo 0)
  echo "$(date "+%F %T") 删除坏件 $(basename "$f") ${sz}B"
  rm -f -- "$f"
done
echo "$(date "+%F %T") E 盘剩余: $(df -h /mnt/e | awk "NR==2{print \$4}")"

# 3) 全面体检
bash "$W/tools/oc-doctor.sh" --quiet >/dev/null 2>&1
DRC=$?
echo "$(date "+%F %T") oc-doctor rc=$DRC"
if [ $DRC -ne 0 ]; then
  bash "$W/tools/oc-doctor.sh" > "$W/state/work/health-block.txt" 2>&1 || true
  echo "$(date "+%F %T") 体检有 FAIL，停止升级（详见 state/work/health-block.txt）"
  timeout 60 bash "$W/tools/notify.sh" "【升级暂停】备份已完，但体检有 FAIL，未升级。详见 state/work/health-block.txt" >/dev/null 2>&1 || true
  exit 5
fi

# 4) 体检绿 → 升级
echo "=== $(date "+%F %T") 体检通过，开始升级 2026.11.6"
bash "$W/tools/upgrade-openclaw.sh" --version=2026.11.6 --force
URC=$?
echo "=== $(date "+%F %T") 升级结束 rc=$URC"
exit $URC