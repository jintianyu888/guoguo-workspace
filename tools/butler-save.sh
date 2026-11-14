#!/usr/bin/env bash
# butler-save.sh — 管家自审/报告统一落盘入口（只写自己工作区的 state/self-review/）
# 用法: echo "正文" | butler-save.sh <管家id> <文件名> [--dir self-review|reports]
set -uo pipefail

AID="${1:-}"; NAME="${2:-}"
if [ $# -ge 2 ]; then shift 2; fi
DIRKIND=self-review
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIRKIND="${2:-self-review}"; shift 2 ;;
    *) shift ;;
  esac
done

case "$AID" in
  maint|backup|model|work|library|hermess|sheet-music|news|law|tax|fitness|english|infoboard|cooking|music|study|project) ;;
  *) echo "ERR: 管家id 不在白名单: $AID" >&2; exit 2 ;;
esac

printf '%s' "$NAME" | grep -qE '^[A-Za-z0-9][A-Za-z0-9._-]{0,59}$' || { echo "ERR: 文件名只允许字母数字点下划线短横线" >&2; exit 2; }
case "$NAME" in *.md) ;; *) NAME="$NAME.md" ;; esac

case "$DIRKIND" in
  self-review|reports) ;;
  *) echo "ERR: --dir 只允许 self-review 或 reports" >&2; exit 2 ;;
esac

case "$AID" in
  maint)  WS=/home/j/openclaw-workspaces/maint ;;
  model)  WS=/home/j/.openclaw/workspace-model ;;
  work)   WS=/home/j/openclaw-workspaces/work ;;
  hermess|sheet-music) WS=/home/j/openclaw-workspaces/sheet-music ;;
  *)      WS="/home/j/openclaw-workspaces/$AID" ;;
esac
[ -d "$WS" ] || { echo "ERR: 工作区不存在 $WS" >&2; exit 3; }

DIR="$WS/state/$DIRKIND"
mkdir -p "$DIR" || exit 3
TMP="$(mktemp "$DIR/.in-XXXXXX")" || exit 4
cat > "$TMP"
BYTES=$(wc -c < "$TMP")
if [ "$BYTES" -gt 204800 ]; then rm -f "$TMP"; echo "ERR: 内容超过 200KB" >&2; exit 5; fi
[ "$BYTES" -gt 0 ] || { rm -f "$TMP"; echo "ERR: 内容为空，拒绝写入" >&2; exit 6; }
OUT="$DIR/$NAME"
mv -f "$TMP" "$OUT"
echo "OK $OUT ${BYTES}B"

