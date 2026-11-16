#!/bin/bash
# backup-retention.sh —— 备份管家 L2 入口：两阶段清理（强制先 dry-run）
# 用法: backup-retention.sh --dry-run | --apply
set -uo pipefail
MODE="${1:---dry-run}"
ROOT=/home/j/.openclaw/workspace
TOOL="$ROOT/tools/backup-prune.py"
if [ -e "$ROOT/state/work/butlers-frozen" ]; then echo "REFUSED: L2 冻结中" >&2; exit 91; fi
[ -x "$TOOL" ] || [ -f "$TOOL" ] || { echo "缺 $TOOL"; exit 2; }
case "$MODE" in
  --dry-run) python3 "$TOOL" ;;
  --apply)
    python3 "$TOOL" > /tmp/br-dry.txt 2>&1 || { echo "dry-run 失败，拒绝 apply"; tail -5 /tmp/br-dry.txt; exit 3; }
    grep -qiE "delete|删除|would delete" /tmp/br-dry.txt || { echo "dry-run 无可删项，无需 apply"; exit 0; }
    python3 "$TOOL" --apply ;;
  *) echo "用法: backup-retention.sh --dry-run|--apply" >&2; exit 2;;
esac
