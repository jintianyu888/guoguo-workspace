#!/usr/bin/env bash
python3 /home/j/.openclaw/workspace/tools/quiet_window.py >/dev/null 2>&1 && exit 0
# self-monitor.sh - 自助体检：内存 / CPU / 磁盘；正常时静默（零 token），超标才输出【告警 + 找原因】
set -u
W=/home/j/.openclaw/workspace
ST="$W/state/self-monitor"; mkdir -p "$ST"
LOG="$ST/history.log"
TS=$(date '+%F %T')

MEM_WARN=90; MEM_CRIT=96   # 2026-09-28 18:3x 主公令：内存警报阈值提高一点（80->90 / 92->96）
SWAP_WARN=70
DISK_WARN=85
LOAD_WARN=120   # load1 占核数百分比

_ml=$(awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{print t, a}' /proc/meminfo)
total=${_ml% *}; avail=${_ml#* }
mem_pct=$(( (total-avail)*100/total ))
_sw=$(awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{print t, f}' /proc/meminfo)
st=${_sw% *}; sf=${_sw#* }
swap_pct=0; [ "${st:-0}" -gt 0 ] && swap_pct=$(( (st-sf)*100/st ))
cores=$(nproc)
load1=$(cut -d' ' -f1 /proc/loadavg)
load_pct=$(awk -v l="$load1" -v c="$cores" 'BEGIN{printf "%d", (l/c)*100}')

disk_bad=""
# 磁盘告警支持「暂停」：state/alert-snooze-disk-until 存 epoch，未过期则整段跳过
disk_bad=$(df -P -x tmpfs -x devtmpfs -x overlay 2>/dev/null | awk 'NR>1 && $6 !~ /^\/mnt\/[fg]$/ {print $6, $5}' | while read -r mnt use; do
  u=${use%\%}
  if [ "$u" -ge "$DISK_WARN" ]; then printf ' %s=%s%%' "$mnt" "$u"; fi
done)
SNZ=$W/state/alert-snooze-disk-until
if [ -f "$SNZ" ] && [ "$(cat "$SNZ" 2>/dev/null)" -gt "$(date +%s)" ] 2>/dev/null; then disk_bad=""; fi

ALERT=0; MSG=""
[ "$mem_pct" -ge "$MEM_WARN" ] && { ALERT=1; MSG="$MSG
· 内存 ${mem_pct}%（阈值 ${MEM_WARN}%）"; }
[ "$swap_pct" -ge "$SWAP_WARN" ] && { ALERT=1; MSG="$MSG
· Swap ${swap_pct}%（阈值 ${SWAP_WARN}%）"; }
[ "$load_pct" -ge "$LOAD_WARN" ] && { ALERT=1; MSG="$MSG
· CPU 负载 ${load1}（${load_pct}%，${cores} 核）"; }
[ -n "$disk_bad" ] && { ALERT=1; MSG="$MSG
· 磁盘偏高：$disk_bad"; }

# Item4（2026-09-30 老板令）：Swap 高时【自动干预】—— 防「一去不回」
if [ "${swap_pct:-0}" -ge 80 ]; then
  SG=$W/state/swap-guard.log
  echo "[$(date '+%F %T')] swap=${swap_pct}% 触发自动干预" >> "$SG"
  avail_mb=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo 2>/dev/null)
  if [ "${avail_mb:-0}" -ge 4096 ]; then
    if /mnt/c/Windows/System32/wsl.exe -d Ubuntu -u root -- sh -c 'swapoff -a && swapon -a' >> "$SG" 2>&1; then
      echo "[$(date '+%F %T')] swap 已重置（原 ${swap_pct}%，空闲 ${avail_mb}MB）" >> "$SG"
    else
      echo "[$(date '+%F %T')] swap 重置失败，见上" >> "$SG"
    fi
  else
    echo "[$(date '+%F %T')] 空闲内存不足（${avail_mb}MB < 4096MB），跳过重置以免 OOM" >> "$SG"
  fi
  echo "$(date '+%F %T') swap=${swap_pct}%" > "$W/state/swap-guard-flag"
fi

gw_pid=$(systemctl --user show openclaw-gateway -p MainPID --value 2>/dev/null)
gw_rss=na
if [ -n "$gw_pid" ] && [ "$gw_pid" != "0" ]; then gw_rss=$(awk '/VmRSS/{printf "%.2fG", $2/1048576}' "/proc/$gw_pid/status" 2>/dev/null); fi
[ -z "$gw_rss" ] && gw_rss=na
gpu_raw=$(timeout 10 /usr/lib/wsl/lib/nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
[ -z "$gpu_raw" ] && gpu_raw=na
printf '%s mem=%s%% swap=%s%% load=%s disk=%s gw_rss=%s gpu=%s\n' "$TS" "$mem_pct" "$swap_pct" "$load1" "${disk_bad:-ok}" "$gw_rss" "$gpu_raw" >> "$LOG"
# 跨天时把前一天汇总进 daily.csv（保留 90 天），避免 3000 行轮转把长历史冲掉
TODAY=$(date +%F)
LASTDAY_FILE="$ST/.last-rollup-day"
LASTDAY=$(cat "$LASTDAY_FILE" 2>/dev/null || echo "")
if [ "$LASTDAY" != "$TODAY" ]; then
  python3 /home/j/.openclaw/workspace/tools/self-monitor-rollup.py >> "$ST/rollup.log" 2>&1 || true
  echo "$TODAY" > "$LASTDAY_FILE"
fi
tail -n 3000 "$LOG" > "$LOG.t" 2>/dev/null && mv "$LOG.t" "$LOG"

[ "$ALERT" -eq 0 ] && exit 0

echo "🔴【自查告警】$TS"
echo -e "$MSG"
echo
echo "【找原因】"
echo "· 内存 TOP5："
ps -eo rss,comm --sort=-rss 2>/dev/null | awk 'NR>1 && NR<=6 {printf "   %6.2f GB  %s\n", $1/1048576, $2}'
echo "· CPU TOP5："
ps -eo pcpu,comm --sort=-pcpu 2>/dev/null | awk 'NR>1 && NR<=6 {printf "   %5.1f%%  %s\n", $1, $2}'
echo "· 网关内存（上限保护）："
systemctl --user show openclaw-gateway -p MemoryCurrent -p MemoryMax 2>/dev/null | sed 's/^/   /'
echo "· 家目录 TOP3 占用："
du -xh --max-depth=1 /home/j 2>/dev/null | sort -rh | head -3 | sed 's/^/   /'
echo
echo "【怎么办】"
if [ "$mem_pct" -ge "$MEM_CRIT" ]; then echo "· 🔴 内存极高 → 我压缩长会话 / 重启网关（硬上限 12G 已兜底）"; else echo "· ⚠️ 内存偏高 → 我盯住长会话，必要时压缩"; fi
echo "· 趋势历史：$LOG"
exit 0