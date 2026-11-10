#!/bin/bash
# verify-backup.sh —— 备份文件哈希校验（2026-10-15 主公令）
# 用法：
#   verify-backup.sh make <文件...>        # 生成 <文件>.sha256 清单 + SHA256SUMS
#   verify-backup.sh check <文件> [清单]    # 校验（默认同名 .sha256）
#   verify-backup.sh cmp <文件A> <文件B>    # 两副本比对（哈希）
# 说明：MD5 有已知碰撞，统一用 SHA256（更硬）。
set -u
ALGO=sha256
case "${1:-}" in
  make)
    shift; for f in "$@"; do
      [ -f "$f" ] || { echo "跳过(不存在): $f"; continue; }
      S=$(date +%s); H=$(${ALGO}sum "$f" | cut -d' ' -f1); E=$(( $(date +%s) - S ))
      printf '%s  %s\n' "$H" "$(basename "$f")" > "$f.${ALGO}"
      printf '%s  %s\n' "$H" "$(basename "$f")" >> "$(dirname "$f")/SHA256SUMS"
      echo "✅ $(basename "$f")  hash=$H  (大小 $(du -h "$f"|cut -f1), 用时 ${E}s)"
    done ;;
  check)
    F="$2"; L="${3:-$F.${ALGO}}"
    [ -f "$L" ] || { echo "❌ 缺清单 $L"; exit 1; }
    WANT=$(cut -d' ' -f1 < "$L"); GOT=$(${ALGO}sum "$F" | cut -d' ' -f1)
    if [ "$WANT" = "$GOT" ]; then echo "✅ 校验通过 $(basename "$F")"; else echo "❌ 校验失败 $(basename "$F")"; exit 2; fi ;;
  cmp)
    A=$(${ALGO}sum "$2" | cut -d' ' -f1); B=$(${ALGO}sum "$3" | cut -d' ' -f1)
    echo "A: $A  $2"; echo "B: $B  $3"
    if [ "$A" = "$B" ]; then echo "✅ 内容完全一致"; else echo "❌ 内容不一致"; fi ;;
  *) sed -n '2,8p' "$0" ;;
esac
