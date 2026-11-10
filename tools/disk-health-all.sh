#!/usr/bin/env bash
# disk-health-all.sh —— 盘位体检总入口（只读）v3 · 2026-10-24 主公令合并
# 判定策略：
#   wsl 段：有警告也返回 1，rc 不可信 -> 只看输出"失败 N>0"
#   eh  段：恒返回 0 -> 只看故障标志
#   nas 段：rc=2 表示超阈值（告警文案只进 notify，stdout 无标志）-> rc 必须采信
set -uo pipefail
W=/home/j/.openclaw/workspace
LOG="$W/state/disk-health-all.log"
TS=$(date '+%F %T')
TMPD=$(mktemp -d)
trap 'rm -rf $TMPD' EXIT
OUTF="$TMPD/all.txt"
NAS_HIT=0
INTERNAL=0

run() {
  local tag="$1"; shift
  local out rc
  echo "## $tag" >>"$OUTF"
  out=$(timeout 1500 "$@" 2>&1); rc=$?
  echo "$out" >>"$OUTF"
  echo "rc=$rc" >>"$OUTF"
  echo "   [$tag] rc=$rc" >&2
  case "$rc" in 124|126|127) INTERNAL=1 ;; esac
  case "$tag" in
    *群晖*) [ "$rc" = "2" ] && NAS_HIT=1 ;;
  esac
}

: >"$OUTF"
run "盘位总览(WSL/C/D/E/H/X)" bash "$W/tools/wsl-disk-health.sh" --quiet
run "E/H 全树比对" bash "$W/tools/eh-health.sh"
run "群晖容量" bash "$W/tools/nas-free-check.sh"

ALERT=0
[ "$NAS_HIT" = "1" ] && ALERT=1
grep -qE "🔴|失败 [1-9][0-9]*|告急|不可达|ERROR|FATAL" "$OUTF" && ALERT=1

{ echo "===== $TS ====="; cat "$OUTF"; } >>"$LOG"
tail -c 300000 "$LOG" >"$LOG.tmp" && mv "$LOG.tmp" "$LOG"

if [ "$ALERT" -eq 1 ]; then
  SUMMARY=$(grep -E "^## |WSL盘位体检|🔴|告急|不可达|失败 [1-9]|ERROR" "$OUTF" | tail -14)
  if timeout 30 bash "$W/tools/notify.sh" --alert "【告警】盘位体检有异常（D/E/H/X/群晖）：$SUMMARY" >/dev/null 2>&1; then
    echo "ALERT=1（告警已投递；退出码 0，避免 cron 每天误报任务失败）"
    exit 0
  fi
  # 告警投递失败绝不允许静默：写状态 + 退出非 0，让 cron 告警接手
  echo "ALERT=1 但告警投递失败（notify.sh 非 0）" >&2
  echo "$TS notify_failed" >> "$W/state/work/disk-health-alert-fail.log"
  exit 4
fi
if [ "$INTERNAL" -eq 1 ]; then
  echo "内部错误：某段返回 124(timeout)/126/127(命令不存在)" >&2
  exit 3
fi
echo "OK 全绿"
exit 0
