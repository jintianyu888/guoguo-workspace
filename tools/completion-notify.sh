#!/bin/bash
# completion-notify.sh —— 每完成一项立刻报「已完成什么 + 下一步做什么」
# 用法: completion-notify.sh --no 123 --did "做了什么(证据)" --next "下一步" [--by main] [--quiet]
set -uo pipefail
W=/home/j/.openclaw/workspace
NO=""; DID=""; NEXT=""; BY="main"; QUIET=0
while [ $# -gt 0 ]; do
  case "$1" in
    --no) NO=$2; shift 2;;
    --did) DID=$2; shift 2;;
    --next) NEXT=$2; shift 2;;
    --by) BY=$2; shift 2;;
    --quiet) QUIET=1; shift;;
    *) shift;;
  esac
done
TITLE=$(python3 - <<EOF
import sqlite3
c=sqlite3.connect("$W/state/tasks/tasks.db")
r=c.execute("select title from tasks where no=?",("${NO:-0}",)).fetchone()
print((r[0] if r else "")[:60])
EOF
)
[ -z "$NEXT" ] && NEXT="继续推进在办任务（见 20:30 晚间简报）"
MSG="✅ 完成 #${NO} ${TITLE}
· 做了什么：${DID:-已按验收标准关闭}
· 下一步：${NEXT}
· 执行人：${BY}"
[ "$QUIET" = "1" ] && { echo "$MSG"; exit 0; }
bash "$W/tools/notify.sh" "$MSG" >/dev/null 2>&1 || bash "$W/tools/notify.sh" "$MSG"
echo "$MSG"
