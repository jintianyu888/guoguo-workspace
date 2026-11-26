#!/bin/bash
# state-db-integrity.sh —— 每日核对 state 库完整性（零 token）。2026-11-26 立
# 背景：11-21 与 11-26 两次 openclaw.sqlite 页级损坏，均由启动时 integrity_check 才发现
set -uo pipefail
export PATH=/usr/bin:/bin:/home/j/.npm-global/bin
W=/home/j/.openclaw/workspace
S=/home/j/.openclaw/state
LOG=$W/state/work/state-db-integrity.log
TMP=$(mktemp -d)
BAD=0
check(){
  src=$1; name=$(basename "$src")
  [ -f "$src" ] || { echo "SKIP $name 不存在" >> "$LOG"; return; }
  cp -f "$src" "$TMP/$name" 2>/dev/null || { echo "WARN $name 复制失败" >> "$LOG"; return; }
  out=$(python3 - "$TMP/$name" <<'PY'
import sqlite3,sys
try:
    c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True)
    print(c.execute('PRAGMA integrity_check').fetchone()[0])
except Exception as e:
    print('ERR '+str(e))
PY
)
  if [ "$out" = "ok" ]; then echo "OK $name" >> "$LOG"; else echo "BAD $name -> $out" >> "$LOG"; BAD=1; fi
}
echo "=== $(date '+%F %T')" >> "$LOG"
check "$S/openclaw.sqlite"
check /home/j/.openclaw/lcm.db
check "$W/state/tasks/tasks.db"
rm -rf "$TMP"
if [ "$BAD" = "1" ]; then
  tail -8 "$LOG" > /tmp/sdb.txt
  bash "$W/tools/notify.sh" "【state 库巡检】发现损坏：$(grep '^BAD' "$LOG" | tail -3 | tr '\n' ';')" >/dev/null 2>&1
  exit 1
fi
exit 0
