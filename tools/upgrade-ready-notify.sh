#!/bin/bash
# upgrade-ready-notify.sh —— 等备份链路彻底收尾，逐项体检，全部通过才提示「可以点升级」
set -u
W=/home/j/.openclaw/workspace
U=${1:-bkm-201107}
LOG=$W/state/work/upgrade-ready.log
say(){ echo "[$(date "+%F %T")] $*" >> "$LOG"; }

say "start watcher for $U"
for i in $(seq 1 240); do systemctl --user is-active --quiet "$U" || break; sleep 30; done
say "unit $U inactive; waiting pushes"
for i in $(seq 1 120); do
  pgrep -f "backup-push-latest|nas-push-archive|backup-mirror-verify|openclaw backup create" >/dev/null 2>&1 || break
  sleep 30
done
sleep 20

FAIL=""
NEW=$(ls -t /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | head -1)
if [ -z "$NEW" ]; then FAIL="$FAIL 无归档"; else
  SZ=$(stat -c%s "$NEW"); AGE=$(( $(date +%s) - $(stat -c%Y "$NEW") ))
  say "archive=$(basename "$NEW") size=$SZ age=${AGE}s"
  [ "$SZ" -gt 60000000000 ] || FAIL="$FAIL 归档偏小($SZ)"
  [ "$AGE" -lt 14400 ] || FAIL="$FAIL 归档不是今天新的"
fi
H=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 http://127.0.0.1:18789/health 2>/dev/null)
[ "$H" = "200" ] || FAIL="$FAIL 网关健康=$H"
for f in .upgrade-running .safe-restart-running .watchdog-pause; do
  [ -f "$W/state/work/$f" ] && FAIL="$FAIL 标志$f存在"
done
FREE=$(df -Pk /home/j | sed -n 2p | tr -s ' ' | cut -d' ' -f4)
[ "${FREE:-0}" -gt 209715200 ] || FAIL="$FAIL 磁盘余量仅${FREE}KB"
Q=$(python3 "$W/tools/backup-quiet.py" status 2>&1 | head -1)
case "$Q" in *静默中*) FAIL="$FAIL 备份静默未恢复";; esac
PG=$(openclaw cron list --json >/dev/null 2>&1; echo $?)

if [ -z "$FAIL" ]; then
  TGT=$(npm view openclaw version 2>/dev/null | tail -1)
  CUR=$(openclaw --version 2>/dev/null | tail -1)
  MSG="✅ 备份已收尾，可以点「一键升级」了
· 新归档：$(basename "$NEW")（$(numfmt --to=iec $SZ)）
· 当前版本：$CUR，目标版本：${TGT:-未知}
· 网关 $H，磁盘余 ${FREE}KB，无冲突标志，静默已恢复
· 点之前刷新一下面板（F5）；升级 5-8 分钟，网关中断 1-2 分钟，失败自动回滚"
else
  MSG="⚠️ 备份已结束但升级条件不满足，先别点：$FAIL
明细：$LOG"
fi
say "verdict FAIL=[$FAIL]"
timeout 90 bash "$W/tools/notify.sh" "$MSG" >/dev/null 2>&1 || say "notify failed"
printf "%s\n" "$MSG" > "$W/state/work/upgrade-ready.txt"
exit 0
