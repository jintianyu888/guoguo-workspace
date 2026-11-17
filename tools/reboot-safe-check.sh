#!/bin/bash
# reboot-safe-check.sh v1.1 (2026-11-17) -- host reboot pre-check for the Windows weekly reboot task.
# Exit 0 = safe to reboot; 1 = backup/mirror/compact running; 2 = idle but gateway unhealthy.
# ASCII output on purpose (consumed by PowerShell task log).
set -u
W=/home/j/.openclaw/workspace
cd "$W" 2>/dev/null || exit 1
REASON=""

if ! flock -n "$W/state/work/backup-quiet.lock" -c true 2>/dev/null; then
  REASON="backup lock held"
fi
if [ -z "$REASON" ] && pgrep -f "openclaw-backup|backup-mirror|backup-push|rsync .*openclaw" >/dev/null 2>&1; then
  REASON="backup/mirror/push process running"
fi
if [ -z "$REASON" ] && pgrep -f "diskpart|Optimize-VHD" >/dev/null 2>&1; then
  REASON="disk compaction running"
fi

if [ -n "$REASON" ]; then
  echo "BUSY: $REASON"
  exit 1
fi

H=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:18789/health 2>/dev/null)
if [ "$H" != "200" ]; then
  echo "IDLE_BUT_UNHEALTHY: gateway health=$H"
  exit 2
fi
echo "OK: idle, gateway health=200"
exit 0
