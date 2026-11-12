#!/usr/bin/env bash
# safe-restart-gateway.sh v4 —— 网关安全重启唯一执行体（2026-10-25 主公令：重启=高危）
# v4 按双审（deepseek-v4-pro + kimi-k3）必改项：
#   - 真存活探针改 HTTP /health 200（ss LISTEN 抓不到事件循环冻结的"假死"）
#   - 网关已挂时不跑依赖网关的体检，直接进入拉起（修复"救火时自我锁死"）
#   - .safe-restart-running 超过 10 分钟视为陈旧标志，自动清理
set -u
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace
LOG=$W/state/work/safe-restart.log
LOCK=$W/state/work/.gateway-ctl.lock
FLAG=$W/state/work/.safe-restart-running
PORT=18789
PAT="dist/index.js gateway"
DRY=0; FORCE=0; ALLOW_DOCTOR=0; REASON="未注明"
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1;; --force) FORCE=1;; --allow-doctor) ALLOW_DOCTOR=1;;
    --reason) REASON="$2"; shift;;
  esac
  shift
done
mkdir -p "$W/state/work"
[ -f "$LOG" ] && [ $(stat -c %s "$LOG" 2>/dev/null || echo 0) -gt 1048576 ] && tail -c 512K "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
log(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
pid_of(){ pgrep -f "$PAT" | head -1; }
http_ok(){ [ "$(timeout 6 curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health" 2>/dev/null)" = "200" ]; }
uc(){ systemctl --user "$@" 2>/dev/null; }
start_gw(){ uc reset-failed openclaw-gateway; uc start openclaw-gateway; }
upgrade_running(){ [ -f "$W/state/work/.upgrade-running" ] || pgrep -af "openclaw update|npm (i|install) -g openclaw|openclaw upgrade" 2>/dev/null | grep -v "update status" | grep -v "upgrade-panel\|safe-restart" | grep -qv pgrep; }
alive(){ [ -n "$(pid_of)" ] && http_ok; }
RESULT=$W/state/work/safe-restart-result.json
# 结果落盘：退出码给看门狗/上层消费（v4-pro 评审要求）
res(){ printf '{"ts":"%s","rc":%s,"reason":"%s","mode":"%s","old_pid":"%s","new_pid":"%s","log":"%s"}\n' \
  "$(date '+%F %T')" "$1" "$REASON" "$2" "${OLD_PID:-}" "$(pid_of)" "$LOG" > "$RESULT"; echo "$1" > "$RESULT.rc"; }

# 陈旧标志清理（评审：SIGKILL 后残留会让看门狗永久失明）
if [ -f "$FLAG" ]; then
  AGE=$(( $(date +%s) - $(stat -c %Y "$FLAG" 2>/dev/null || echo 0) ))
  if [ "$AGE" -gt 600 ]; then log "清理陈旧标志 .safe-restart-running（$AGE 秒）"; rm -f "$FLAG"; fi
fi

exec 9>"$LOCK"
flock -n 9 || { echo "another gateway-ctl running, exit"; exit 0; }
if [ -f "$FLAG" ] && [ "$FORCE" = "0" ]; then echo "safe-restart already running"; exit 0; fi

GW_DOWN=0; alive || GW_DOWN=1
log "===== safe-restart v4 | reason=$REASON dry=$DRY force=$FORCE gw_down=$GW_DOWN ====="
log "systemd: $(systemctl --user show openclaw-gateway -p NRestarts -p Result -p ActiveState -p SubState --value 2>/dev/null | tr '\n' ' ')"

FAIL=""
if [ "$GW_DOWN" = "0" ]; then
  timeout 120 openclaw cron list --json >/dev/null 2>&1 || FAIL="$FAIL cron_cli_down"
  VAL=$(timeout 120 openclaw config validate 2>&1 | tail -1)
  echo "$VAL" | grep -qi "valid" || FAIL="$FAIL config_invalid"
else
  log "网关当前不可用 -> 跳过依赖网关的体检（cron/config），直接进入拉起"
  VAL="skipped(gateway_down)"
fi
HH=$(date +%H)
if [ "$FORCE" = "0" ] && { [ "$HH" = "04" ] || [ "$HH" = "05" ]; }; then FAIL="$FAIL quiet_window"; fi
if [ "$FORCE" = "0" ] && pgrep -f "backup-(tier1-critical|archive|mirror-verify)|backup-with-quiet" >/dev/null 2>&1; then FAIL="$FAIL backup_running"; fi
if [ "$FORCE" = "0" ] && upgrade_running; then FAIL="$FAIL upgrade_running"; fi
if [ "$FORCE" = "0" ] && [ -f "$W/state/work/.watchdog-pause" ]; then FAIL="$FAIL maintenance_pause"; fi
# 2026-11-12 决策组 D-20261112-002 条件落地：TMPDIR 指向 /dev/shm/oc-tmp，
#   tmpfs 写满是硬失败，故重启前必须确认：容量够、目录在、可写。
#   任一不达标即放弃本次重启（沿用失败即取消的既有语义）。
SHM_AVAIL_M=$(df -m --output=avail /dev/shm 2>/dev/null | tail -1 | tr -dc '0-9')
if [ -z "${SHM_AVAIL_M:-}" ] || [ "${SHM_AVAIL_M:-0}" -lt 8192 ]; then FAIL="$FAIL shm_too_small(${SHM_AVAIL_M:-0}M)"; fi
if [ ! -d /dev/shm/oc-tmp ]; then FAIL="$FAIL shm_tmpdir_missing"; fi
if [ -d /dev/shm/oc-tmp ]; then
  probe="/dev/shm/oc-tmp/.preflight-$$"
  if ! ( : > "$probe" ) 2>/dev/null; then FAIL="$FAIL shm_not_writable"; else rm -f "$probe"; fi
fi
OLD_PID=$(pid_of)
log "体检: config=[$VAL] old_pid=${OLD_PID:-none} failed=[${FAIL:-无}]"
if [ -n "$FAIL" ]; then
  log "前置体检不通过，放弃：$FAIL"
  timeout 40 bash "$W/tools/notify.sh" --alert "SAFE-RESTART blocked: $FAIL (reason=$REASON)" >/dev/null 2>&1 || true
  res 4 blocked; exit 4
fi
if [ "$DRY" = "1" ]; then log "dry-run：不执行"; res 0 dryrun; exit 0; fi

: > "$FLAG"
trap 'rm -f "$FLAG"' EXIT
if [ -n "${OLD_PID:-}" ]; then
  log "systemctl --user restart"
  uc reset-failed openclaw-gateway
  timeout 400 systemctl --user restart openclaw-gateway >>"$LOG" 2>&1
else
  log "按 start 处理"
  start_gw >>"$LOG" 2>&1
fi
verify(){ [ -n "$(pid_of)" ] || return 1; http_ok || return 1; return 0; }
OK=1
for i in $(seq 1 36); do if verify; then OK=0; break; fi; sleep 5; done
if [ "$OK" != "0" ]; then
  log "180s 未就绪，自动拉起（最多 2 次）"
  for i in 1 2; do start_gw >>"$LOG" 2>&1 || true; sleep 15; if verify; then OK=0; break; fi; done
fi
if [ "$OK" != "0" ] && [ "$ALLOW_DOCTOR" = "1" ]; then
  log "仍失败，doctor --fix"
  timeout 600 openclaw doctor --fix >>"$LOG" 2>&1 || true
  start_gw >>"$LOG" 2>&1 || true
  sleep 20
  verify && OK=0
fi
NEW_PID=$(pid_of)
if [ "$OK" = "0" ]; then
  log "OK new_pid=$NEW_PID old=${OLD_PID:-none} http=200"
  # v5 (2026-10-31 双审必改项): 四项验收 = PID / HTTP / 模型链 / 任务层
  ACC=$(timeout 200 bash "$W/tools/restart-acceptance.sh" "${OLD_PID:-0}" 2>&1); ACCRC=$?
  log "ACCEPTANCE: $ACC"
  if [ "$ACCRC" -ne 0 ]; then
    log "WARN 四项验收未全绿 (rc=$ACCRC), 按不完整重启处理"
    timeout 60 bash "$W/tools/notify.sh" --alert "GATEWAY-RESTARTED-BUT-ACCEPTANCE-NOT-GREEN ($REASON): $ACC" >/dev/null 2>&1 || true
  else
    timeout 40 bash "$W/tools/notify.sh" "GATEWAY-RESTARTED-OK ($REASON) 验收四项全绿" >/dev/null 2>&1 || true
  fi
  # 记录本次实际停机耗时（供下次“预计耗时”中位数使用）
  if [ -n "${MAINT_START_EPOCH:-}" ]; then
    ELAPSED=$(( $(date +%s) - MAINT_START_EPOCH ))
    if [ "$ELAPSED" -lt 0 ]; then ELAPSED=0; fi
    timeout 20 bash "$W/tools/pre-restart-check.sh" --commit "$ELAPSED" --action restart --reason "$REASON" >/dev/null 2>&1 || true
  fi
  res 0 ok; exit 0
else
  log "FAIL 进程/HTTP 未恢复"
  timeout 60 bash "$W/tools/notify.sh" --alert "GATEWAY-DOWN after restart: http://127.0.0.1:$PORT/health not 200; auto-start+doctor failed; log $LOG" >/dev/null 2>&1 || true
  res 3 fail; exit 3
fi
