#!/usr/bin/env bash
# restart-gateway.sh —— 网关重启唯一入口（2026-10-25 主公令：重启=高危，必须走这里）
# 用法: bash tools/restart-gateway.sh --reason "说明" [--force] [--dry-run] [--allow-doctor]
# 它做三件事：冲突检查 -> 交给 systemd-run 在网关外执行 -> 打印查看进度的命令
set -u
W=/home/j/.openclaw/workspace
SAFE=$W/tools/safe-restart-gateway.sh
UNIT=safe-restart-$(date +%Y%m%d-%H%M%S)

if [ -f "$W/state/work/.upgrade-running" ]; then
  if [ "${ALLOW_UPGRADE_RESTART:-0}" = "1" ]; then
    echo "ALLOW: 升级流程自持重启（ALLOW_UPGRADE_RESTART=1，跳过 .upgrade-running 拦截）"
  else
    echo "REFUSE: 升级进行中 (.upgrade-running)"; exit 5
  fi
fi
pgrep -af "openclaw update|npm (i|install) -g openclaw|openclaw upgrade" 2>/dev/null | grep -v "update status" | grep -qv pgrep && { echo "REFUSE: 检测到升级进程"; exit 5; }
[ -f "$W/state/work/.safe-restart-running" ] && { echo "REFUSE: 已有安全重启在进行"; exit 5; }
[ -f "$W/state/work/.watchdog-pause" ] && { echo "REFUSE: 维护暂停开关存在"; exit 5; }

# —— 权威冲突检查前置（kimi M2：预告必须在确认能重启之后发，否则夜间必误报）——
MIN=$(date +%H%M); MIN=$((10#$MIN))
if [ "$MIN" -ge 400 ] && [ "$MIN" -le 605 ]; then echo "REFUSE: 静默窗 04:00–06:05"; exit 5; fi
# 备份占用判定改用锁文件 + flock 实测（确定性信号；避免 pgrep 子串把命令行里带关键词的进程误判）
for _lf in "$W/state/work/backup-hash-job.lock" "$W/state/work/backup-drill.lock" "$W/state/work/backup-quiet.lock" "$W/state/work/backup-retain.lock"; do
  [ -e "$_lf" ] || continue
  if ! flock -n "$_lf" true 2>/dev/null; then echo "REFUSE: 备份进行中（$(basename "$_lf") 被占用）"; exit 5; fi
done

# —— 重启前预告：维护管家账号推送；失败不阻塞重启；--dry-run 不推 ——
REASON_ARG="-"; prev=""
for a in "$@"; do
  if [ "$prev" = "--reason" ]; then REASON_ARG="$a"; break; fi
  prev="$a"
done
case " $* " in
  *" --check-only "*)
    echo "MODE=check-only (不执行重启)"
    timeout 200 bash "$W/tools/pre-restart-check.sh" --dry-run --action restart --item "网关重启" --reason "${REASON_ARG:-check-only}"
    rc1=$?
    echo "--- 模型链体检 ---"
    ( cd "$W" && timeout 60 python3 tools/modelchain-check.py ); rc2=$?
    echo "PREFLIGHT_RC=$rc1/$rc2  (0=全绿 2=本地模型不可查/未知)"
    if [ "$rc1" -eq 0 ] && [ "$rc2" -eq 0 ]; then echo "CHECK_ONLY_OK"; exit 0; fi
    echo "CHECK_ONLY_NOT_GREEN"; exit 6
    ;;
esac
case " $* " in
  *" --dry-run "*) : ;;
  *) timeout 120 bash "$W/tools/pre-restart-check.sh" --push --action restart --item "网关重启" --reason "$REASON_ARG" >/dev/null 2>&1 || echo "预告推送失败（不阻塞重启）" ;;
esac
START_EPOCH=$(date +%s)

echo "提交安全重启单元: $UNIT"
systemd-run --user --unit="$UNIT" --collect --property=TimeoutStartSec=infinity --setenv=MAINT_START_EPOCH="$START_EPOCH" bash "$SAFE" "$@"
rc=$?
echo "rc=$rc"
echo "进度: tail -f $W/state/work/safe-restart.log"
echo "结果: cat $W/state/work/safe-restart-result.json"
exit $rc
