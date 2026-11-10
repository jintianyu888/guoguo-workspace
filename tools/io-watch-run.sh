#!/bin/bash
# io-watch-run.sh —— systemd 单元包装（2026-11-02 迁移）
# 原 cron delivery.mode=none：io-watch.sh 只把告警 print 到 stdout，等于被丢弃。
# 迁移后补上真实投递（走 notify.sh --alert，失败回落网关 CLI 并记失败日志）。
# 脚本自身有状态去重（只在"出现/解除"时输出）。
set -u
W=/home/j/.openclaw/workspace
out=$(bash "$W/tools/io-watch.sh" 2>&1)
rc=$?
if [ -n "$out" ]; then
  bash "$W/tools/notify.sh" --alert "$out" >/dev/null 2>&1 \
    || { echo "$(date '+%F %T') NOTIFY_FAIL $out" >> "$W/state/io-watch-notify-fail.log"; printf '%s\n' "$out"; }
fi
exit $rc
