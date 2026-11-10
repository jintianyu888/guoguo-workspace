#!/usr/bin/env bash
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
cd /home/j/.openclaw/workspace || exit 1
sleep 60
RESTART=$(journalctl --user -u openclaw-gateway --since "12:17" --no-pager 2>/dev/null | grep -c 'starting feishu\[backup\]')
PROBE=$(timeout 90 openclaw channels status --probe 2>&1 | grep -i 'Feishu backup')
BLOCKED=$(journalctl --user -u openclaw-gateway --since "12:17" --no-pager 2>/dev/null | grep -c 'blocked unauthorized sender ou_19e43ddd')
{
  echo "== $(date '+%F %T') =="
  echo "通道重载次数: $RESTART"
  echo "仍被拦条数: $BLOCKED"
  echo "探测: $PROBE"
} > state/work/backup-channel-probe.txt
timeout 60 bash tools/notify.sh "备份管家通道复查：重载 $RESTART 次 · 拦截 $BLOCKED 条 · $PROBE" >/dev/null 2>&1
