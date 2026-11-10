#!/usr/bin/env bash
# gw-mem-window.sh - 02:30 静默窗内存巡检：留诊断快照，RSS 触线才重启（走 restart-gateway.sh）
set -u
W=/home/j/.openclaw/workspace
cd "$W" || exit 1
PID=$(systemctl --user show openclaw-gateway -p MainPID --value)
[ -z "$PID" ] || [ "$PID" = "0" ] && { echo "gateway 未运行"; exit 1; }
RSS_G=$(awk "/VmRSS/{printf \"%.2f\", \$2/1048576}" /proc/$PID/status)
REP="state/reports/gw-mem-diag-$(date +%Y%m%d-%H%M).md"
{
  echo "# 网关内存快照 $(date "+%F %T")"
  echo "PID=$PID RSS=${RSS_G}G"
  systemctl --user show openclaw-gateway -p MemoryCurrent -p MemoryHigh -p MemoryMax
  echo "## smaps_rollup"
  head -8 /proc/$PID/smaps_rollup 2>/dev/null
  echo "## 子进程 RSS top10"
  ps -eo pid,ppid,rss,comm --sort=-rss | head -11
} > "$REP" 2>&1
TH=${GW_RESTART_THRESHOLD:-9.0}
QUIET=0; python3 tools/quiet_window.py >/dev/null 2>&1 && QUIET=1
LASTF=state/work/.gw-mem-restart-last
BREAK=0
if [ -f "$LASTF" ]; then L=$(cat "$LASTF"); NOW=$(date +%s); [ $((NOW-L)) -lt 86400 ] && BREAK=1; fi
HIT=$(awk -v r="$RSS_G" -v t="$TH" "BEGIN{print (r>=t)?1:0}")
echo "快照 $REP | RSS=${RSS_G}G 阈值=${TH}G 触发=$HIT 静默窗=$QUIET 24h已重启=$BREAK"
if [ "$HIT" != "1" ]; then
  timeout 30 bash tools/notify.sh --alert "网关RSS ${RSS_G}G 未触线(${TH}G)，仅留快照 $REP" >/dev/null 2>&1 || true
  exit 0
fi
if [ "$QUIET" = "1" ]; then
  timeout 30 bash tools/notify.sh --alert "网关RSS ${RSS_G}G 触线但处备份静默窗，本轮不重启；快照 $REP" >/dev/null 2>&1 || true
  exit 0
fi
if [ "$BREAK" = "1" ]; then
  timeout 30 bash tools/notify.sh --alert "网关RSS ${RSS_G}G 触线但24h内已重启(熔断)，交人工；快照 $REP" >/dev/null 2>&1 || true
  exit 0
fi
if [ "${DRY:-0}" = "1" ]; then echo "[dry-run] 将建锚点并重启"; exit 0; fi
ANCH="state/rollback/gw-pre-restart-$(date +%Y%m%d-%H%M).tar.gz"
tar czf "$ANCH" -C / home/j/.openclaw/openclaw.json home/j/.config/systemd/user/openclaw-gateway.service home/j/.config/systemd/user/openclaw-gateway.service.d 2>/dev/null || true
ls -t state/rollback/gw-pre-restart-*.tar.gz 2>/dev/null | tail -n +4 | xargs -r rm -f
echo "$(date +%s)" > "$LASTF"
timeout 40 bash tools/notify.sh --alert "网关RSS ${RSS_G}G 触线，静默窗受控重启；回滚锚点 $ANCH" >/dev/null 2>&1 || true
if [ "$HIT" = "1" ]; then
  bash tools/notify.sh --alert "网关RSS ${RSS_G}G 触线(阈值${TH}G)，按三审决议在静默窗受控重启；快照 $REP" >/dev/null 2>&1
  bash tools/restart-gateway.sh --reason "RSS ${RSS_G}G 触线(-$TH G)，三审决议计划内回收"
else
  bash tools/notify.sh --alert "网关RSS ${RSS_G}G 未触线(阈值${TH}G)，仅留快照：$REP" >/dev/null 2>&1 || true
fi