#!/bin/bash
# verify-fresh-archive.sh —— 校验最新全量归档完整性（2026-10-16）
LOG=/home/j/.openclaw/workspace/state/archive-verify.log
F=$(ls -t /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | head -1)
{
  echo "=== START $(date '+%F %T') ==="
  echo "文件: $F ($(stat -c%s "$F" 2>/dev/null) 字节)"
  openclaw backup verify "$F" 2>&1 | tail -20
  echo "verify_rc=$?"
  echo "=== DONE $(date '+%F %T') ==="
} >> "$LOG" 2>&1
