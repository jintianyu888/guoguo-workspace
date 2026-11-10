#!/usr/bin/env bash
# 回收站登记/移入脚本 —— move 而非 delete，绝不真删
set -euo pipefail

WS="/home/j/.openclaw/workspace"
TRASH="$WS/回收站"
MANIFEST="$TRASH/manifest.jsonl"
ITEMS="$TRASH/items"

usage() {
  cat <<'EOF'
用法: trash-add.sh <路径或条目名> --reason "..." --type task|file|schedule [--source "来源路径"] [--agent 经手人]

  --type file     <路径> 是文件/目录，move 进 回收站/items/YYYY-MM/（保留原名），并记账
  --type task     <条目名> 是任务名，只记账（不搬文件）
  --type schedule <条目名> 是日程名，只记账（不搬文件）

可选: --source 来源路径（默认空）; --agent 经手人（默认 main）
EOF
}

TYPE=""; REASON=""; SOURCE=""; AGENT="main"; TARGET=""
while [ $# -gt 0 ]; do
  case "$1" in
    --reason) REASON="${2:-}"; shift 2 ;;
    --type) TYPE="${2:-}"; shift 2 ;;
    --source) SOURCE="${2:-}"; shift 2 ;;
    --agent) AGENT="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) if [ -z "$TARGET" ]; then TARGET="$1"; else echo "多余参数: $1" >&2; usage; exit 2; fi; shift ;;
  esac
done

[ -z "$TARGET" ] && { echo "缺少路径或条目名" >&2; usage; exit 2; }
[ -z "$REASON" ] && { echo "缺少 --reason" >&2; usage; exit 2; }
case "$TYPE" in task|file|schedule) ;; *) echo "缺少或非法 --type (task|file|schedule)" >&2; usage; exit 2;; esac

mkdir -p "$TRASH" "$ITEMS"
NOW=$(date '+%Y-%m-%dT%H:%M:%S%z')
MONTH=$(date '+%Y-%m')

DEST=""; NAME="$TARGET"
if [ "$TYPE" = "file" ]; then
  [ -e "$TARGET" ] || { echo "路径不存在: $TARGET" >&2; exit 1; }
  mkdir -p "$ITEMS/$MONTH"
  BASE=$(basename "$TARGET")
  DEST="$ITEMS/$MONTH/$BASE"
  if [ -e "$DEST" ]; then DEST="$ITEMS/$MONTH/${BASE}.$(date '+%H%M%S')"; fi
  mv "$TARGET" "$DEST"
  NAME="$BASE"
  SOURCE="${SOURCE:-$TARGET}"
fi

python3 - "$MANIFEST" "$NOW" "$TYPE" "$NAME" "$SOURCE" "$REASON" "$AGENT" "$DEST" <<'PY'
import json, sys
manifest, now, typ, name, source, reason, agent, dest = sys.argv[1:9]
label = {"task": "任务", "file": "文件", "schedule": "日程"}.get(typ, typ)
rec = {"时间": now, "类型": label, "type": typ, "名称": name, "来源路径": source,
       "为什么废弃": reason, "经手人": agent, "移入路径": dest or ""}
with open(manifest, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
print(f"已记账: {label} · {name}" + (f" -> {dest}" if dest else ""))
PY
