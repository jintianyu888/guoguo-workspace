#!/bin/bash
[ -z "${BASH_VERSION:-}" ] && exec /bin/bash "$0" "$@"
# 瞬态 30 分钟恢复：LOCK 存在时执行；先撤掉维护 drop-in，再启动，验证端口才清锁
set -uo pipefail
U=openclaw-gateway
DROPIN=/home/j/.config/systemd/user/openclaw-gateway.service.d/zz-maint.conf
LOCK=/home/j/.openclaw/state/maintenance.flag
W=/home/j/.openclaw/workspace
[ -f "$LOCK" ] || exit 0
# 双审共识(2026-10-23)：延长窗口优先——内容非数字/空一律视为已过期（fail-open 偏向恢复）
EXT="$W/state/work/maint-extended-until"
if [ -f "$EXT" ]; then
  until_ts=$(cat "$EXT" 2>/dev/null || true)
  now=$(date +%s)
  if [ -n "$until_ts" ] && [[ "$until_ts" =~ ^[0-9]+$ ]] && [ "$now" -lt "$until_ts" ]; then
    echo "[$(date '+%F %T')] AUTORESUME SKIP 维护延长中至 $(date -d @"$until_ts" '+%F %T')" >> "$W/state/work/maintenance.log"
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
    echo "[$(date '+%F %T')] AUTORESUME OK 网关已恢复 Restart=$(systemctl --user show $U -p Restart --value)" >> "$W/state/work/maintenance.log"
    bash "$W/tools/notify.sh" "维护窗口超时（30 分钟），网关已自动恢复" >/dev/null 2>&1
    exit 0
  fi
  sleep 1
done
echo "[$(date '+%F %T')] AUTORESUME FAIL 网关未上线，保留维护锁" >> "$W/state/work/maintenance.log"
bash "$W/tools/notify.sh" "维护超时自动恢复失败：网关未上线，锁已保留，请人工检查" >/dev/null 2>&1
exit 1
