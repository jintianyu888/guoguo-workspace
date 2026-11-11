#!/bin/bash
# evening-upgrade.sh — 18:20 半价窗自动升级（2026-11-11 主公令：晚上升级）
# 用法: evening-upgrade.sh [--dry]
set -uo pipefail
export PATH=/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/evening-upgrade.log
TARGET=2026.11.3
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
notify(){ bash "$WS/tools/notify.sh" "$1" >/dev/null 2>&1 || true; }
say "===== 晚间升级开始 目标=$TARGET dry=${1:-no} ====="
if pgrep -f "rsync.*openclaw-backups" >/dev/null 2>&1; then
  say "跳过：备份进程在跑"; notify "晚间升级跳过：备份进程占用，明晚再试"; exit 0
fi
[ -f "$WS/state/work/.maintenance" ] && { say "跳过：维护标记存在"; exit 0; }
avail=$(df -BG --output=avail /home/j | tail -1 | tr -dc "0-9")
if [ "${avail:-0}" -lt 50 ]; then say "跳过：磁盘仅 ${avail}G"; notify "晚间升级跳过：磁盘不足 ${avail}G"; exit 0; fi
say "① 预升级备份"
if timeout 2400 bash "$WS/tools/pre-upgrade-backup.sh" >>"$LOG" 2>&1; then
  say "   预升级备份 rc=0"
else
  say "   预升级备份失败 rc=$?，改用当日全量归档+面板四库快照作回滚点"
fi
[ "${1:-}" = "--dry" ] && { say "演练结束，不安装"; exit 0; }
say "② 执行升级"
if bash "$WS/tools/upgrade-panel.sh" --target "$TARGET" >>"$LOG" 2>&1; then
  ver=$(openclaw --version 2>/dev/null | tail -1)
  jobs=$(openclaw cron list --json 2>/dev/null | grep -c '"id"' || echo 0)
  say "③ 完成：$ver，cron 条目 $jobs"
  notify "OpenClaw 已升级到 $TARGET｜版本 $ver｜cron 条目 $jobs｜日志 state/work/evening-upgrade.log"
else
  rc=$?
  say "③ 升级失败 rc=$rc（upgrade-panel 应已自动回滚）"
  notify "晚间升级失败 rc=$rc，已按脚本回滚；请查 state/work/evening-upgrade.log"
fi
say "===== 晚间升级结束 ====="
