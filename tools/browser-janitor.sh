#!/bin/bash
# browser-janitor.sh —— 清理僵尸 Chromium（2026-11-07 主公令：别开一堆窗口不关）
# 判定：headless Chrome 根进程，父进程为 1（已脱离 Playwright 驱动）且存活 > IDLE_MIN
# 只杀这类，active 会话有 node 父进程，不会被误伤
set -uo pipefail
W=/home/j/.openclaw/workspace
LOG=$W/state/work/browser-janitor.log
IDLE_MIN=${IDLE_MIN:-15}
MAXMB=${MAXMB:-2500}   # 超过这个总内存也强制清一次
mkdir -p "$(dirname "$LOG")"

now=$(date +%s); killed=0; freed=0
for pid in $(pgrep -f 'chrome-linux64/chrome|chrome-headless-shell' 2>/dev/null); do
  [ -r /proc/$pid/stat ] || continue
  ppid=$(awk '{print $4}' /proc/$pid/stat 2>/dev/null)
  et=$(ps -o etimes= -p "$pid" 2>/dev/null | tr -d ' ')
  [ -n "${et:-}" ] && [ "$et" -gt $((IDLE_MIN*60)) ] || continue
  cmd=$(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null)
  case "$cmd" in *--type=*) continue;; esac   # 只处理根进程
  gwp=$(pgrep -f 'openclaw.*gateway|MainThread' 2>/dev/null | head -1)
  if [ "${ppid:-1}" = "1" ] || { [ -n "${gwp:-}" ] && [ "${ppid:-0}" = "$gwp" ]; }; then
    rss=$(awk '/VmRSS/{print $2}' /proc/$pid/status 2>/dev/null)
    pkill -TERM -P "$pid" 2>/dev/null; kill -TERM "$pid" 2>/dev/null
    sleep 1; kill -KILL "$pid" 2>/dev/null
    killed=$((killed+1)); freed=$((freed+${rss:-0}/1024))
    echo "$(date '+%F %T') kill pid=$pid age=${et}s rss=${rss:-0}kB head=$(echo "$cmd" | cut -c1-80)" >> "$LOG"
  fi
done
totalmb=$(ps -eo rss,args | grep -iE '[c]hrome' | awk '{s+=$1} END{printf "%d", s/1024}')
if [ "${totalmb:-0}" -gt "$MAXMB" ]; then
  echo "$(date '+%F %T') 警告：Chrome 总内存 ${totalmb}MB 超阈值 ${MAXMB}MB，请人工确认是否泄漏" >> "$LOG"
fi
[ "$killed" -gt 0 ] && echo "$(date '+%F %T') 清理 $killed 个僵尸 Chrome 根进程，约释放 ${freed}MB；当前总 ${totalmb}MB" >> "$LOG"
exit 0
