#!/usr/bin/env bash
# backup-watch.sh —— 盯指定 systemd 单元结束，然后飞书报结果（独立于网关）
set -u
U=${1:?unit}
while systemctl --user is-active --quiet "$U"; do sleep 30; done
RC=$(systemctl --user show -p ExecMainStatus --value "$U" 2>/dev/null)
echo "[watch] $U 结束 rc=$RC at $(date "+%F %T")"
MSG="全量备份结束：$U rc=${RC:-?}。日志 journalctl --user -u $U；归档目录 /mnt/d/openclaw-backups"
if [ "${RC:-1}" = "0" ]; then MSG="✅ $MSG"; else MSG="⚠️ $MSG（非 0，需查看）"; fi
timeout 60 bash /home/j/.openclaw/workspace/tools/notify.sh "$MSG" >/dev/null 2>&1 || true
exit 0
