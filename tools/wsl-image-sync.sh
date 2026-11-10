#!/bin/bash
# wsl-image-sync.sh —— 保证 E:\wsl-backup 与 H:\wsl-backup 两份整机镜像始终一致（E 为准，H 补齐）
# 规则：文件名+大小一致 → 再比首尾 1MB md5；任一不符 → Robocopy 从 E 覆盖到 H
# 用法：wsl-image-sync.sh [--check|--apply] [--notify]
#   默认 --check（只报差异，不写）；--apply 才真正补拷
set -u
E=/mnt/e/wsl-backup
H=/mnt/h/wsl-backup
LOG=/home/j/.openclaw/workspace/state/work/wsl-image-sync.log
LEDGER=/home/j/.openclaw/workspace/state/work/wsl-image-sync-ledger.jsonl
ROBO=/mnt/c/Windows/System32/Robocopy.exe
MODE=check; NOTIFY=0
for a in "$@"; do
  case "$a" in
    --apply) MODE=apply ;;
    --check) MODE=check ;;
    --notify) NOTIFY=1 ;;
  esac
done
mkdir -p "$H" "$(dirname "$LOG")"
echo "[$(date '+%F %T')] === mode=$MODE ===" >> "$LOG"
RC=0; FIXED=0; DIFFS=0

sig() { # 首尾 1MB md5
  local f=$1 sz
  sz=$(stat -c %s "$f" 2>/dev/null) || { echo "MISSING"; return; }
  local h1 h2
  h1=$(dd if="$f" bs=1M count=1 status=none 2>/dev/null | md5sum | cut -d' ' -f1)
  h2=$(dd if="$f" bs=1M skip=$(( sz/1048576 - 1 )) count=1 status=none 2>/dev/null | md5sum | cut -d' ' -f1)
  echo "$sz:$h1:$h2"
}

copy_one() { # $1=相对名
  local name=$1
  echo "[$(date '+%F %T')] 补拷 $name" >> "$LOG"
  # robocopy 只能"目录→目录 + 文件名过滤"，不能拿单文件当源目录（否则 267 目录名无效）
  "$ROBO" "E:\\wsl-backup" "H:\\wsl-backup" "$name" /J /NP /NFL /NDL /R:2 /W:5 >> "$LOG" 2>&1
  local rc=$?
  if [ $rc -ge 8 ]; then
    echo "[$(date '+%F %T')] ❌ Robocopy rc=$rc $name" >> "$LOG"; RC=1; return 1
  fi
  FIXED=$((FIXED+1))
  printf '{"ts":"%s","file":"%s","action":"copy","rc":%d}\n' "$(date -Iseconds)" "$name" "$rc" >> "$LEDGER"
  return 0
}

for f in "$E"/*; do
  [ -f "$f" ] || continue
  name=$(basename "$f")
  case "$name" in *.part|*.tmp) continue;; esac
  se=$(sig "$f"); sh=$(sig "$H/$name")
  if [ "$se" = "$sh" ]; then
    echo "[$(date '+%F %T')] ✅ 一致 $name ($(echo "$se" | cut -d: -f1))" >> "$LOG"
    continue
  fi
  DIFFS=$((DIFFS+1))
  echo "[$(date '+%F %T')] ⚠ 不一致 $name  E=$se  H=$sh" >> "$LOG"
  if [ "$MODE" = apply ]; then copy_one "$name" || true; fi
done

# H 上有 E 没有的（只报，不删）
for f in "$H"/*; do
  [ -f "$f" ] || continue
  name=$(basename "$f")
  [ -f "$E/$name" ] || echo "[$(date '+%F %T')] ℹ H 独有（不删，待主公定）$name" >> "$LOG"
done

echo "[$(date '+%F %T')] === 结束 diffs=$DIFFS fixed=$FIXED rc=$RC ===" >> "$LOG"
if [ "$NOTIFY" = 1 ] && [ "$DIFFS" -gt 0 ]; then
  timeout 30 sh /home/j/.openclaw/workspace/tools/notify.sh "🖼 E/H 整机镜像：$DIFFS 个不一致，已修 $FIXED 个（mode=$MODE）" >/dev/null 2>&1 || true
fi
exit $RC
