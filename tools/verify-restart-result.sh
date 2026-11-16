#!/bin/bash
# verify-restart-result.sh v1.0 (2026-11-16) —— 08:20 核对 08:00 重启是否真的发生
set -u
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
W=/home/j/.openclaw/workspace
cd "$W" || exit 3
PID=$(systemctl --user show -p MainPID --value openclaw-gateway 2>/dev/null)
ST=$(ps -o lstart= -p "$PID" 2>/dev/null)
STS=$(date -d "$ST" +%s 2>/dev/null || echo 0)
CUT=$(date -d 'today 08:00' +%s)
H=$(timeout 10 curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/health 2>/dev/null)
if [ "$STS" -ge "$CUT" ]; then
  bash tools/notify.sh "【重启核对】08:00 重启已生效（PID $PID，启动于 $ST），health=$H" >/dev/null 2>&1 || true
  echo "$(date '+%F %T') OK pid=$PID st=$ST health=$H" >> state/work/restart-verify.log
else
  bash tools/notify.sh "【重启核对·未生效】08:00 窗口没重启成功：网关仍启动于 $ST。原因看 state/work/restart-window.log 与 pre-restart-selfcheck.txt" >/dev/null 2>&1 || true
  echo "$(date '+%F %T') FAIL pid=$PID st=$ST health=$H" >> state/work/restart-verify.log
fi
exit 0