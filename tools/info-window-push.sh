#!/usr/bin/env bash
# info-window-push.sh —— 渲染信息窗并推送到飞书（零 token）
# 用法: info-window-push.sh [--force]   （--force 忽略 08:00-23:00 时间窗）
set -u
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace
OUT=$W/state/info-window/card.png
LOG=$W/state/info-window/push.log
# 飞书 open_id 按应用隔离：走哪个账号发，就必须用那个应用空间的 open_id
ACC="${ACC:-maint}"
case "$ACC" in
  maint) TO=user:ou_008693513eb3b36f292fcfaa7a8b57b3 ;;
  default) TO=user:ou_74fec7bc81cc6ec6d2b4de1c0967923b ;;
  *) echo "未知账号 $ACC"; exit 2 ;;
esac
mkdir -p "$W/state/info-window"
exec 9>"$W/state/info-window/.push.lock"; flock -n 9 || exit 0
H=$(date +%H)
if [ "${1:-}" != "--force" ] && { [ "$H" -lt 8 ] || [ "$H" -ge 23 ]; }; then exit 0; fi
python3 "$W/tools/info-window-card.py" "$OUT" >>"$LOG" 2>&1 || { echo "[$(date '+%F %T')] render_fail" >>"$LOG"; exit 3; }
MSG="📊 信息窗 $(date '+%m-%d %H:%M')"
timeout 90 openclaw message send --channel feishu --account "$ACC" --target "$TO" --media "$OUT" --message "$MSG" >>"$LOG" 2>&1
RC=$?
echo "[$(date '+%F %T')] push rc=$RC size=$(stat -c %s "$OUT" 2>/dev/null)" >>"$LOG"
exit $RC
