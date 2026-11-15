#!/bin/bash
# preflight.sh v1.0 — 危险动作前置闸门（2026-11-15 主公令）
# 用法: preflight.sh <del|cron|restart|config> [目标]
# 退出码: 0 放行 / 非0 拦截（拦截原因写 stderr）
set -uo pipefail
W=/home/j/.openclaw/workspace
LOG=$W/state/work/preflight.jsonl
ACT=${1:-}; TGT=${2:-}
ok()   { printf '%s\n' "$*"; rec pass "$*"; exit 0; }
die()  { printf '❌ %s\n' "$*" >&2; rec fail "$*"; exit 3; }
rec()  { mkdir -p "$(dirname "$LOG")"; printf '{"at":"%s","action":"%s","target":"%s","result":"%s","note":"%s"}\n' "$(date '+%F %T')" "$ACT" "$TGT" "$1" "$2" >> "$LOG"; }

case "$ACT" in
  del|delete)
    [ -n "$TGT" ] || die '缺少目标路径'
    case "$TGT" in
      /home/j/*|/mnt/x/*|/mnt/d/*|/mnt/e/*|/mnt/h/*|/mnt/nas/*) ;;
      *) die "目标不在允许范围: $TGT" ;;
    esac
    [ -e "$TGT" ] || die "目标不存在: $TGT"
    sz=$(du -sm "$TGT" 2>/dev/null | awk '{print $1}')
    if [ "${sz:-0}" -gt 5000 ]; then
      echo "⚠ 目标 ${sz}MB，需先证明有副本：" >&2
      echo "  请用 tools/backup-retain-*.sh 的隔离流程，或先 sha256 抽样比对" >&2
      rec fail "大目标未走隔离流程 ${sz}MB"; exit 4;
    fi
    ok "放行删除 $TGT (${sz:-?}MB)；请用 mv 到 _quarantine 或回收站，不要 rm -rf"
    ;;
  cron)
    out=$(cd "$W" && timeout 120 python3 tools/schedule-plan.py overlaps 2>&1 | tail -1)
    case "$out" in *'0 处重叠'*) ok "放行：调度 $out";; *) die "改 cron 后出现重叠: $out";; esac
    ;;
  restart)
    if pgrep -fa 'daily-backup|backup-run|nas-push' >/dev/null 2>&1; then die '备份正在运行，禁止重启'; fi
    hhmm=$(date +%H%M)
    if [ "$((10#$hhmm))" -ge 100 ] && [ "$((10#$hhmm))" -le 230 ]; then die '红区 01:00-02:30'; fi
    if [ "$((10#$hhmm))" -ge 400 ] && [ "$((10#$hhmm))" -le 605 ]; then die '静默窗 04:00-06:05'; fi
    ok '放行重启（仍需走 tools/restart-gateway.sh）'
    ;;
  config)
    ok '放行配置变更：必须先用 openclaw config patch --dry-run'
    ;;
  --self-test)
    printf 'self-test: '
    bash -n "$0" && echo 'syntax ok' 
    exit 0
    ;;
  *)
    echo 'usage: preflight.sh <del|cron|restart|config> [target]' >&2
    exit 2
    ;;
esac
