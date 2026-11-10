#!/bin/bash
# daily-health.sh v1.0 — 每日系统自检 + 稳定性审查 合并入口（2026-10-26 主公令）
# 顺序：每日系统自检 → 稳定性审查（周日自动 --deep）→ 汇总落盘 → 仅在异常时告警（6h 去重）
set -u -o pipefail
WS=/home/j/.openclaw/workspace
OUT=$WS/state/health
mkdir -p "$OUT"
D=$(date +%F); TS=$(date '+%F %T')
exec 9>"$WS/state/work/daily-health.lock"
if ! flock -n 9; then
  timeout 30 bash "$WS/tools/notify.sh" --alert "【告警】每日体检：上一轮仍在运行，本轮跳过" "" >/dev/null 2>&1 || true
  exit 3
fi

DEEP=""
[ "$(date +%u)" = "7" ] && DEEP="--deep"

echo "== [1/2] 每日系统自检 $TS ==" > "$OUT/run-$D.log"
# 2026-10-27 修（维护日清·双审通过 glm-5.3 + kimi-k3.1-pro）：600s < 内层 900s 预算导致自检被腰斩；
# 9>&- 让子进程不继承锁 fd 9，避免被 timeout 杀掉父进程后残留 tar 孤儿长期持锁（曾致次轮 exit 3）。
timeout -k 15 1500 bash "$WS/tools/daily-selfcheck.sh" 9>&- >> "$OUT/run-$D.log" 2>&1; RC1=$?
case "$RC1" in 124|137) pkill -f "tools/backup-drill.sh" 2>/dev/null || true; pkill -f "tar tzf /mnt/d/openclaw-backups" 2>/dev/null || true; echo "· [cleanup] 自检超时(rc=$RC1)，已清理 drill 残留进程" >> "$OUT/run-$D.log";; esac
echo "" >> "$OUT/run-$D.log"
echo "== [2/2] 稳定性审查 $DEEP ==" >> "$OUT/run-$D.log"
timeout -k 15 1500 bash "$WS/tools/stability-check.sh" $DEEP 9>&- >> "$OUT/run-$D.log" 2>&1; RC2=$?

SUM=$(python3 - <<'PY' 2>/dev/null
import json
try:
    d=json.load(open('/home/j/.openclaw/workspace/state/stability/latest.json'))
    c=d.get('counts') or d.get('summary') or {}
    print('PASS %s / WARN %s / FAIL %s' % (c.get('pass','?'),c.get('warn','?'),c.get('fail','?')))
except Exception:
    print('稳定性结果不可读')
PY
)
{
  echo "每日体检 $TS  自检rc=$RC1 稳定rc=$RC2"
  echo "稳定判定: $SUM"
  echo "--- 自检尾部 ---"
  tail -12 "$OUT/run-$D.log" | grep -v '^$'
} > "$OUT/$D.txt"
cat "$OUT/$D.txt"

if [ $RC1 -ne 0 ] || [ $RC2 -ne 0 ]; then
  KEY=$OUT/.last-alert
  NOW=$(date +%s)
  LA=0; [ -f "$KEY" ] && LA=$(cat "$KEY" 2>/dev/null || echo 0)
  if [ $((NOW-LA)) -gt 21600 ]; then
    timeout 30 bash "$WS/tools/notify.sh" --alert "【告警】每日体检异常 自检 rc=$RC1 / 稳定 rc=$RC2" "详见 $OUT/$D.txt" >/dev/null 2>&1 || true
    echo "$NOW" > "$KEY"
  fi
fi
exit 0
