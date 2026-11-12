#!/usr/bin/env bash
# shm-guard.sh — /dev/shm 容量守卫（零 token）
# 2026-11-12 立：网关 TMPDIR 已指向 /dev/shm/oc-tmp（09:08 生效），
#   而 /dev/shm 与 /tmp 同为 23.5G tmpfs，写满是硬失败（ENOSPC），故设水位告警。
# 阈值：>=70% 告警；>=85% 额外清理 oc-tmp 下超 2 小时的浏览器/回放残留
# 只动 /dev/shm/oc-tmp 下的临时残留，绝不删 oc-cache / oc-tmp 本体
set -u
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/shm-guard.log
STAMP=$WS/state/work/.shm-alert-stamp
mkdir -p "$(dirname "$LOG")"

pct=$(df --output=pcent /dev/shm 2>/dev/null | tail -1 | tr -dc '0-9')
[ -z "${pct:-}" ] && exit 0
avail=$(df -h --output=avail /dev/shm 2>/dev/null | tail -1 | tr -d ' ')
echo "$(date '+%F %T') pct=$pct avail=$avail" >> "$LOG"

if [ "$pct" -ge 85 ]; then
  before=$(du -sm /dev/shm/oc-tmp 2>/dev/null | cut -f1)
  find /dev/shm/oc-tmp -mindepth 1 -maxdepth 1 -type d -mmin +120 \
       \( -name 'playwright-artifacts-*' -o -name 'oc-br-*' -o -name 'org.chromium.*' \) \
       -exec rm -rf {} + 2>/dev/null
  after=$(du -sm /dev/shm/oc-tmp 2>/dev/null | cut -f1)
  pct=$(df --output=pcent /dev/shm 2>/dev/null | tail -1 | tr -dc '0-9')
  echo "$(date '+%F %T') CLEANED oc-tmp ${before}MB->${after}MB pct=${pct}" >> "$LOG"
fi

if [ "$pct" -ge 70 ]; then
  # 6 小时内只推一次，避免刷屏
  if [ ! -f "$STAMP" ] || [ $(( $(date +%s) - $(stat -c %Y "$STAMP") )) -gt 21600 ]; then
    touch "$STAMP"
    bash "$WS/tools/notify.sh" "内存盘告警：/dev/shm 已用 ${pct}%（剩余 ${avail}），网关临时目录就在这块盘上。已自动清理超 2 小时的浏览器残留，若继续上涨请叫我看。" >> "$LOG" 2>&1
  fi
fi
exit 0
