#!/usr/bin/env bash
# encrypt-ssh-backup.sh —— 用口令把 .ssh 备份包加密（B 方案）
# 用法: encrypt-ssh-backup.sh <口令>   —— 口令只经参数传入，脚本不落盘
set -uo pipefail
PASS="${1:-}"
[ -n "$PASS" ] || { echo '用法: encrypt-ssh-backup.sh <口令>'; exit 2; }
TS=$(date +%Y%m%d-%H%M)
ok=0
for SRC in /home/j/.openclaw/backup-extra/ssh-config-*; do
  [ -d "$SRC" ] || continue
  OUT="${SRC%/}.tar.gz.gpg"
  tar czf - -C "$SRC" . 2>/dev/null | gpg --batch --yes --symmetric --cipher-algo AES256 --passphrase "$PASS" -o "$OUT" 2>/dev/null \
    && { echo "  ✅ 加密完成: $OUT ($(du -h "$OUT" | cut -f1))"; ok=$((ok+1)); } \
    || echo "  ❌ 失败: $SRC"
done
echo "加密包数: $ok"
[ "$ok" -gt 0 ] && echo '⚠️ 提醒：原始（未加密）目录仍在本机，确认无碍后再决定是否挪走'
