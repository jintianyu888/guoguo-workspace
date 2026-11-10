#!/bin/bash
# proc-watch-run.sh —— systemd 单元包装（2026-11-02 迁移）
# 2026-11-02 主公令：告警一律走果果告警（独立 webhook → 主应用），维护管家只收报告
# 因此这里不再指定 maint 目标，交 notify.sh --alert 统一路由。
set -u
W=/home/j/.openclaw/workspace
out=$(bash "$W/tools/proc-watch.sh" 2>&1)
rc=$?
if [ -n "$out" ]; then
  NOTIFY_FROM=maint \
    bash "$W/tools/notify.sh" --alert "$out" >/dev/null 2>&1 \
    || { echo "$(date '+%F %T') NOTIFY_FAIL $out" >> "$W/state/proc-watch-notify-fail.log"; printf '%s\n' "$out"; }
fi
exit $rc
