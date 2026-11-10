#!/usr/bin/env bash
# backup-ops.sh v1 —— 备份管家唯一执行入口（2026-10-31 主公授权）
# 只暴露只读/演练动词；真删一律不在此脚本内。
# 用法: bash tools/backup-ops.sh <verb>
set -uo pipefail
W=/home/j/.openclaw/workspace
LOG=$W/state/work/backup-ops.log
V="${1:-}"
say(){ echo "$*"; echo "[$(date '+%F %T')] $V | $*" >> "$LOG"; }
reject(){ echo "拒绝：未知动词 '$V'。可用: status report verify retain-dry drill-last space"; exit 2; }

case "$V" in
  status)
    say "== 盘位水位 =="
    df -h /mnt/d /mnt/e /mnt/h /mnt/x / 2>/dev/null | tail -6
    say "== 群晖 =="
    timeout 25 ssh -o BatchMode=yes -o ConnectTimeout=8 nas 'df -h /volume1 | tail -1' 2>&1 | tail -1
    say "== 最近归档 =="
    ls -t /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | head -3 | while read -r f; do echo "  $(basename "$f") $(du -h "$f" | cut -f1) $(date -r "$f" '+%F %H:%M')"; done
    say "== 保留配置 =="
    grep -E '^[[:space:]]*(export[[:space:]]+)?(KEEP_|WEEKLY)' "$W/tools/retention.env" 2>/dev/null
    ;;
  report)      bash "$W/tools/backup-report.sh" 2>&1 | tail -40 ;;
  verify)      bash "$W/tools/backup-mirror-verify.sh" 2>&1 | tail -30; echo "rc=$?" ;;
  retain-dry)  DRY_RUN=1 bash "$W/tools/backup-retain.sh" 2>&1 | tail -30 ;;
  drill-last)  ls -t "$W"/state/backup-drill/*.md 2>/dev/null | head -1 | xargs -r sed -n '1,40p' ;;
  space)       du -sh /mnt/d/openclaw-backups /mnt/e/openclaw-backups /mnt/h/openclaw-backups /mnt/x/openclaw-backups 2>/dev/null ;;
  *) reject ;;
esac
