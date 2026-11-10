#!/usr/bin/env bash
# backup-precheck.sh —— 01:00 全量备份前 10 分钟预检（只读，不修任何东西）
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/work/backup-precheck.log
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
FAIL=0
say "=== 备份预检开始 ==="

for d in / /mnt/d /mnt/e /mnt/nas /mnt/h; do
  [ -d "$d" ] || { say "⚠️ $d 未挂载"; FAIL=1; continue; }
  av=$(df -Pk "$d" | awk 'NR==2{print int($4/1024/1024)}')
  say "  $d 可用 ${av}G"
  [ "$av" -lt 120 ] && { say "⚠️ $d 可用空间不足 120G"; FAIL=1; }
done

[ -e "$W/state/work/.watchdog-pause" ] && say "  watchdog pause: 存在（备份期间正常）" || say "  watchdog pause: 无"
for l in backup-quiet backup-drill backup-hash-job; do
  p=$W/state/work/$l.lock
  if [ -e "$p" ] && fuser "$p" >/dev/null 2>&1; then say "⚠️ 锁被占用: $l"; FAIL=1; fi
done
pgrep -f 'tar -czf.*openclaw' >/dev/null 2>&1 && { say "⚠️ 已有打包进程在跑"; FAIL=1; }
[ -n "${OC_SQLITE_PROBE_TIMEOUT_MS:-}" ] && say "  探针超时=${OC_SQLITE_PROBE_TIMEOUT_MS}ms" || say "  探针超时=未设置(脚本内默认 180000)"
h=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:18789/health)
say "  gateway health=$h"
[ "$h" = "200" ] || FAIL=1
say "=== 结论: $([ $FAIL -eq 0 ] && echo OK || echo 有问题) ==="
[ $FAIL -eq 0 ] || echo "备份预检发现问题，详见 $LOG"
exit $FAIL
