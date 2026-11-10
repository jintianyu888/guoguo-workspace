#!/bin/bash
# io-stuck-run.sh —— systemd 单元包装（2026-11-02 迁移）
# 背景：原 cron 任务 delivery.mode=none，io-stuck-watch.py 只把告警 print 到 stdout，
#       等于告警被丢弃、没人收到。这里补上真实投递：有输出就走 notify.sh --alert。
# 回滚：systemctl --user disable --now io-stuck.timer && openclaw automations enable bf082793-e399-4d30-9ee6-34b4d1eab48d
set -u
W=/home/j/.openclaw/workspace

out=$(python3 "$W/tools/io-stuck-watch.py" --alert-seconds 120 2>&1)
rc=$?

# 测试钩子：IO_STUCK_TEST=1 时注入一条假告警，用于验证投递链路（生产环境不设此变量）
if [ "${IO_STUCK_TEST:-0}" = "1" ]; then
  out="🧊 IO 哨兵：通道自检（这是一条测试告警，非真实卡死）"
fi

if [ -n "$out" ]; then
  if ! bash "$W/tools/notify.sh" --alert "$out" >/dev/null 2>&1; then
    echo "$(date '+%F %T') NOTIFY_FAIL $out" >> "$W/state/io-stuck-notify-fail.log"
    printf '%s\n' "$out"
  fi
fi
exit $rc
