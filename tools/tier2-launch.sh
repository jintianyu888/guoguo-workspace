#!/bin/bash
# 用 systemd-run 把 T2 中间备份甩到网关外跑，cron 只负责拉起，立即返回。
# 原因：command 型 cron 固定 1800s 超时，T2 单次 >30 分钟必被掐。
set -u
WS=/home/j/.openclaw/workspace
UNIT=oc-tier2-$(date +%Y%m%d%H%M)
LOG=$WS/state/work/tier2.log
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
if systemctl --user is-active --quiet "oc-tier2-" 2>/dev/null; then
  echo "T2 已在跑，跳过"
  exit 0
fi
if systemctl --user list-units --all --no-legend "oc-tier2-*" 2>/dev/null | grep -q "oc-tier2-.*.service.*running"; then
  echo "T2 已在跑，跳过"
  exit 0
fi
echo "== $(date '+%F %T') 拉起 $UNIT ==" >> "$LOG"
systemd-run --user --collect --unit="$UNIT" --description="T2 中间备份"   /bin/bash -lc "sh $WS/tools/backup-tier2-medium.sh" >> "$LOG" 2>&1
rc=$?
echo "launch rc=$rc unit=$UNIT"
exit $rc
