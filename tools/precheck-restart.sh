#!/bin/bash
# precheck-restart.sh v1.0 (2026-11-16) —— 08:00 重启窗口前 10 分钟预检
# 目的：把阻塞项提前暴露，避免 08:00 才发现被拦
set -u
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
W=/home/j/.openclaw/workspace
cd "$W" || exit 3
OUT=$W/state/work/precheck-restart.txt
LINES=()
SC=$(timeout 240 bash tools/console-cmd.sh selfcheck 2>&1)
V=$(printf '%s\n' "$SC" | grep -oE 'PASS [0-9]+ / WARN [0-9]+ / FAIL [0-9]+' | tail -1)
LINES+=("自检: ${V:-读取失败}")
printf '%s\n' "$SC" > "$OUT"
MC=$(timeout 90 python3 tools/modelchain-check.py 2>&1); MRC=$?
LINES+=("模型链: rc=$MRC $(printf '%s' "$MC" | grep -oE 'MODELCHAIN_[A-Z]+' | head -1)")
BUSY=""
for f in backup-hash-job backup-drill backup-quiet backup-retain; do
  lf="$W/state/work/$f.lock"
  [ -e "$lf" ] || continue
  flock -n "$lf" true 2>/dev/null || BUSY="$BUSY $f"
done
if [ -n "$BUSY" ]; then LINES+=("备份锁: 占用$BUSY → 08:00 会被拒"); else LINES+=("备份锁: 全空闲"); fi
BA=$(ls -t /mnt/d/openclaw-backups/*openclaw-backup.tar.gz 2>/dev/null | head -1)
if [ -n "$BA" ]; then LINES+=("最近备份: $(( ( $(date +%s) - $(stat -c %Y "$BA") ) / 3600 ))h 前"); fi
H=$(timeout 10 curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/health 2>/dev/null)
LINES+=("网关 health: $H")
MSG="【08:00重启·10分钟前预检】"
for l in "${LINES[@]}"; do MSG="$MSG
· $l"; done
case "$V" in *'FAIL 0'*) OK=1;; *) OK=0;; esac
if [ "$OK" = 1 ] && [ "$MRC" = 0 ] && [ -z "$BUSY" ] && [ "$H" = 200 ]; then
  MSG="$MSG
结论: 全绿，将按窗口重启"
else
  MSG="$MSG
结论: 有阻塞，需人工处理（明细 $OUT）"
fi
printf '%s\n' "$MSG" >> "$OUT"
[ "${1:-}" = "--no-notify" ] || bash tools/notify.sh "$MSG" >/dev/null 2>&1 || true
exit 0