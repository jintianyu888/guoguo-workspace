#!/usr/bin/env bash
# r24-xhs-ondemand.sh —— R24：小红书只按需查乐谱，不许有定时任务
set -u
n=$(openclaw cron list --json 2>/dev/null | grep -ci 'xhs' || true)
t=$(systemctl --user list-timers --all --no-pager 2>/dev/null | grep -ci 'xhs' || true)
if [ "${n:-0}" -gt 0 ] || [ "${t:-0}" -gt 0 ]; then
  echo "R24 违规：检测到小红书相关定时任务（cron=$n timer=$t），应改成按需触发"
  exit 1
fi
echo "R24 通过：小红书无任何定时任务（仅按需）"
