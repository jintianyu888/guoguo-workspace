#!/usr/bin/env bash
# agent-msg.sh v1 (2026-10-31) — 管家之间固定联络渠道（不依赖网关会话）
# 用法:
#   agent-msg.sh whoami                      # 列出所有管家与工作区
#   agent-msg.sh send <收件人> <正文>          # 投递到对方 workspace/inbox/
#   agent-msg.sh list <收件人>                # 看对方待处理
#   agent-msg.sh read <收件人> <文件名>        # 读一条
#   agent-msg.sh ack  <收件人> <文件名>        # 标记已处理（移到 inbox/.done/）
set -uo pipefail
REG=/home/j/.openclaw/state/agents-registry.json
IDX=/home/j/.openclaw/state/agent-msg-index.jsonl
SELF="${AGENT_ID:-main}"
cmd="${1:-whoami}"; shift || true

ws_of() {
  python3 - "$REG" "$1" <<'PY'
import json,sys
reg=json.load(open(sys.argv[1]))
print(reg.get(sys.argv[2],""))
PY
}

case "$cmd" in
  whoami)
    python3 - "$REG" <<'PY'
import json,sys
reg=json.load(open(sys.argv[1]))
for k in sorted(reg): print(f"{k:16s} {reg[k]}")
PY
    ;;
  send)
    to="${1:?收件人}"; shift; body="$*"
    WS=$(ws_of "$to")
    if [ -z "$WS" ]; then echo "ERR: 未知管家 $to"; exit 2; fi
    mkdir -p "$WS/inbox"
    ts=$(date '+%Y%m%d-%H%M%S')
    f="$WS/inbox/${ts}-${SELF}.md"
    { echo "# 来自 ${SELF} · $(date '+%F %T')"; echo; echo "$body"; } > "$f"
    printf '{"ts":"%s","from":"%s","to":"%s","file":"%s"}\n' "$(date '+%FT%T')" "$SELF" "$to" "$f" >> "$IDX"
    echo "OK -> $f"
    ;;
  list)
    to="${1:?收件人}"; WS=$(ws_of "$to")
    [ -d "$WS/inbox" ] || { echo "空"; exit 0; }
    ls -1 "$WS/inbox" 2>/dev/null | grep -v '^\.' | head -20
    ;;
  read)
    to="${1:?收件人}"; f="${2:?文件名}"; WS=$(ws_of "$to")
    [ -f "$WS/inbox/$f" ] || { echo "ERR: 无此文件"; exit 2; }
    cat "$WS/inbox/$f"
    ;;
  ack)
    to="${1:?收件人}"; f="${2:?文件名}"; WS=$(ws_of "$to")
    [ -f "$WS/inbox/$f" ] || { echo "ERR: 无此文件"; exit 2; }
    mkdir -p "$WS/inbox/.done"
    mv "$WS/inbox/$f" "$WS/inbox/.done/"
    echo "ACK $f"
    ;;
  *)
    echo "未知指令: $cmd（whoami|send|list|read|ack）"; exit 2 ;;
esac
