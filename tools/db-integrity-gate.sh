#!/bin/bash
# db-integrity-gate.sh —— 升级/迁移后 state 库完整性闸门（2026-11-26 立）
# 用法: db-integrity-gate.sh [db路径...]；默认检查 openclaw.sqlite / lcm.db / tasks.db
# rc=0 全部 ok；rc=1 有损坏（打印明细）
set -uo pipefail
DBS="$@"
[ -z "$DBS" ] && DBS="/home/j/.openclaw/state/openclaw.sqlite /home/j/.openclaw/lcm.db /home/j/.openclaw/workspace/state/tasks/tasks.db"
BAD=0
for db in $DBS; do
  [ -f "$db" ] || continue
  out=$(timeout 90 python3 - "$db" <<'PY'
import sqlite3,sys
try:
    c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True)
    print(c.execute('PRAGMA integrity_check').fetchone()[0])
except Exception as e:
    print('ERR '+str(e))
PY
)
  if [ "$out" = "ok" ]; then echo "OK $(basename "$db")"; else echo "BAD $(basename "$db") -> $(echo "$out" | head -1)"; BAD=1; fi
done
[ "$BAD" = "0" ] && echo "GATE_PASS" || echo "GATE_FAIL"
exit $BAD
