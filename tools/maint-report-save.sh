#!/usr/bin/env bash
# maint-report-save.sh — 维护管家报告落盘入口（只能写 workspace/state/maint/）
# 用法: echo "..." | maint-report-save.sh <name>   name 限 [a-z0-9-]，最多 40 字符
set -uo pipefail
NAME="${1:-}"
printf '%s' "$NAME" | grep -qE '^[a-z0-9][a-z0-9-]{0,39}$' || { echo "ERR: 名称只允许小写字母数字与短横线" >&2; exit 2; }
DIR=/home/j/.openclaw/workspace/state/maint
mkdir -p "$DIR" || exit 3
OUT="$DIR/$NAME.md"
TMP=$(mktemp "$DIR/.tmp.XXXXXX") || exit 3
cat > "$TMP" || { rm -f "$TMP"; exit 4; }
BYTES=$(wc -c < "$TMP")
if [ "$BYTES" -gt 204800 ]; then rm -f "$TMP"; echo "ERR: 报告超过 200KB" >&2; exit 5; fi
[ "$BYTES" -gt 0 ] || { rm -f "$TMP"; echo "ERR: 内容为空，拒绝写入" >&2; exit 6; }
mv -f "$TMP" "$OUT"
echo "OK $OUT ${BYTES}B"
