#!/bin/bash
[ -z "${BASH_VERSION:-}" ] && exec /bin/bash "$0" "$@"
# 持久哨兵（oc-maint-guard.timer 每 10 分钟，开机 3 分钟后首次）
# 场景1：维护 drop-in 存在且有锁超过 60 分钟 → 恢复
# 场景2：维护 drop-in 存在但没有锁（例如 WSL 重启丢了瞬态定时器）→ 直接恢复
set -uo pipefail
U=openclaw-gateway
DROPIN=/home/j/.config/systemd/user/openclaw-gateway.service.d/zz-maint.conf
LOCK=/home/j/.openclaw/state/maintenance.flag
W=/home/j/.openclaw/workspace
LOG=$W/state/work/maintenance.log
[ -f "$DROPIN" ] || exit 0

ACT=0
if [ -f "$LOCK" ]; then
  since=$(cat "$LOCK" 2>/dev/null || echo 0)
  now=$(date +%s)
  [ $((now - since)) -ge 3600 ] && ACT=1
else
  ACT=1
fi
[ "$ACT" = 1 ] || exit 0
# 双审共识(2026-10-23)：延长窗口优先——内容非数字/空一律视为已过期（fail-open 偏向恢复）
EXT=/home/j/.openclaw/workspace/state/work/maint-extended-until
if [ -f "$EXT" ]; then
  until_ts=$(cat "$EXT" 2>/dev/null || true)
  now=$(date +%s)
  if [ -n "$until_ts" ] && [[ "$until_ts" =~ ^[0-9]+$ ]] && [ "$now" -lt "$until_ts" ]; then
    echo "[$(date '+%F %T')] GUARD SKIP 维护延长中至 $(date -d @"$until_ts" '+%F %T')" >> "$LOG"
    exit 0
  fi
fi

rm -f "$DROPIN"
systemctl --user daemon-reload
systemctl --user start "$U" >/dev/null 2>&1
for i in $(seq 1 150); do
  if ss -tln 2>/dev/null | grep -q ':18789'; then
    rm -f "$LOCK"
    rm -f "$EXT"
    echo "[$(date '+%F %T')] GUARD OK 已恢复网关 Restart=$(systemctl --user show $U -p Restart --value)" >> "$LOG"
    bash "$W/tools/notify.sh" "维护模式超时，已自动恢复网关（Restart 已还原）" >/dev/null 2>&1
    exit 0
  fi
  sleep 1
done
echo "[$(date '+%F %T')] GUARD FAIL 恢复失败，保留锁" >> "$LOG"
bash "$W/tools/notify.sh" "持久哨兵恢复网关失败，请人工介入" >/dev/null 2>&1
exit 1
