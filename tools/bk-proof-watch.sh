#!/bin/bash
# bk-proof-watch.sh —— 等备份单元结束 → 判定 → 还原 dist 补丁 → 报可升级（2026-11-06）
set -uo pipefail
W=/home/j/.openclaw/workspace
U="${1:-bk-proof-083934.service}"
OUT=$W/state/work/bk-proof-verdict.txt
for i in $(seq 1 480); do
  st=$(systemctl --user is-active "$U" 2>/dev/null)
  [ "$st" = "active" ] || [ "$st" = "activating" ] || break
  sleep 60
done
RCS=$(systemctl --user show "$U" -p ExecMainStatus --value 2>/dev/null)
NEW=$(ls -t /mnt/e/openclaw-backups/*.tar.gz 2>/dev/null | head -1)
SZ=$(stat -c %s "$NEW" 2>/dev/null || echo 0)
MTIME=$(stat -c %y "$NEW" 2>/dev/null | cut -d" " -f1)
TODAY=$(date +%F)
VERDICT=FAIL; REASON=""
if [ "$RCS" = "0" ] && [ "$SZ" -gt 90000000000 ] && [ "$MTIME" = "$TODAY" ]; then
  VERDICT=PASS; REASON="rc=0，新归档 $(basename "$NEW") $(numfmt --to=iec $SZ) 生成于今日"
else
  REASON="rc=${RCS:-?} size=$SZ mtime=$MTIME（要求 rc=0、>90G、今日）"
fi
bash "$W/tools/sqlite-probe-timeout-patch.sh" revert >> "$W/state/work/bk-proof-watch.log" 2>&1
sleep 2
PRE=$(bash "$W/tools/upgrade-preflight.sh" 2>&1 | tail -1)
{
  echo "时间: $(date "+%F %T")"
  echo "备份判定: $VERDICT —— $REASON"
  echo "补丁: 已还原（升级后才可重打）"
  echo "升级前置: $PRE"
  echo "归档: $NEW"
} > "$OUT"
MSG="📦 备份验证 $VERDICT
$REASON

补丁已还原为原版。
$PRE"
timeout 90 bash "$W/tools/notify.sh" "$MSG" >/dev/null 2>&1 || true
if [ "$VERDICT" = "PASS" ]; then
  timeout 90 bash "$W/tools/notify.sh" "👉 现在可以点「升级」了（2026.10.10 → 2026.11.1），点完我盯日志。" >/dev/null 2>&1 || true
fi
