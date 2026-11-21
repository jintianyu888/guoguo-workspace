#!/bin/bash
# nas-push-queue.sh —— 群晖补推队列（v2：单实例、逐份校验、已一致跳过）
set -uo pipefail
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/nas-push.log
NAS=nas
mkdir -p "$WS/state/work"
say(){ echo "$(date "+%F %T") $*" >> "$LOG"; }
exec 8>"$WS/state/work/nas-queue.lock"; flock -n 8 || { say "队列已在运行，退出"; exit 0; }
AV=$(ssh -q -o BatchMode=yes -o ConnectTimeout=15 $NAS "df -k /volume1 | awk 'NR==2{print \$4}'" 2>/dev/null)
say "=== 队列开始 群晖可用 ${AV:-未知}KB ==="
if [ -n "${1:-}" ]; then
  LIST="$1"
else
  # 2026-11-21 修正：原来默认是两个写死的 10-18 文件名，源文件早已不存在 →
  # 每天定时任务都在推 ghost 文件、必然失败，最新归档从没上过群晖。
  # 现在默认取本机最新的 3 份归档（按时间倒序），已有副本的会被 push-one 自动跳过。
  LIST=$(ls -t /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | head -3 | xargs -r -n1 basename | tr '\n' ' ')
  [ -z "$LIST" ] && { say "本地无归档可推，退出"; exit 0; }
fi
OK=0; FAIL=0; SKIP=0
for N in $LIST; do
  say "-> $N"
  bash $WS/tools/push-one.sh "$N"; rc=$?
  case $rc in
    0) if tail -3 "$LOG" | grep -q "远端已一致"; then SKIP=$((SKIP+1)); say "skip $N"; else OK=$((OK+1)); say "ok $N"; fi;;
    *) FAIL=$((FAIL+1)); say "fail $N rc=$rc";;
  esac
done
say "=== 队列结束 成功 $OK 跳过 $SKIP 失败 $FAIL ==="
if [ $FAIL -gt 0 ]; then bash $WS/tools/notify.sh "群晖补推：成功 $OK 跳过 $SKIP 失败 $FAIL（详见 state/work/nas-push.log）" >/dev/null 2>&1 || true; fi
exit 0