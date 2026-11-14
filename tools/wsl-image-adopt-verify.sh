#!/bin/bash
# wsl-image-adopt-verify.sh -- 07:00 复核 systemd-run 托管采纳是否成功；成功则 verifier 关单 999
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/work/wsl-image.log
log() { echo "[$(date '+%F %T')] [adopt-verify] $*" >> "$LOG"; echo "$*"; }

if systemctl --user is-active --quiet wsl-image-adopt; then
  log "仍在运行，未到验收时点；待 08:00 自派工复核"
  exit 0
fi

ok=0
grep -q "ADOPT_OK ubuntu-20261114.tar" "$LOG" && ok=$((ok+1))
bash "$W/tools/wsl-image-sync.sh" --check >/dev/null 2>&1
grep -q "一致 ubuntu-20261114.tar" "$W/state/work/wsl-image-sync.log" && ok=$((ok+1))
E=$(stat -c %s /mnt/e/wsl-backup/ubuntu-20261114.tar 2>/dev/null || echo 0)
H=$(stat -c %s /mnt/h/wsl-backup/ubuntu-20261114.tar 2>/dev/null || echo 0)
[ "$E" -gt 50000000000 ] && [ "$E" = "$H" ] && ok=$((ok+1))
log "复核结果 ok=$ok/3 E=${E}B H=${H}B"

if [ "$ok" -eq 3 ]; then
  cd "$W" && python3 tools/tasks-db.py done 999 --by verifier --why "11月档镜像落地：tar 全量扫描无截断 + E/H 双份同大小 + 首尾签名一致（${E}B）" >> "$LOG" 2>&1
  log "已关单 999"
  bash "$W/tools/notify.sh" "✅ WSL 整机镜像 11 月档验收通过并关单" "ubuntu-20261114.tar ${E} 字节，E/H 双份" >/dev/null 2>&1
  exit 0
fi
log "ADOPT_VERIFY_PARTIAL 未通过（见 wsl-image-sync.log / 上方日志）"
bash "$W/tools/notify.sh" "⚠ WSL 镜像 11 月档验收未通过" "ok=$ok/3 E=${E}B H=${H}B，详见 state/work/wsl-image.log" >/dev/null 2>&1
exit 1
