#!/usr/bin/env bash
# maint-db-read.sh — 维护管家只读查库入口（SQLite 只读 URI 打开，只允许 SELECT/WITH/EXPLAIN）
# 用法: maint-db-read.sh <ledger|tasks|lcm|main> "<SQL>"
set -uo pipefail
case "${1:-}" in
  ledger) DB=/home/j/.openclaw/workspace/state/ledger/ledger.db ;;
  tasks)  DB=/home/j/.openclaw/workspace/state/tasks/tasks.db ;;
  lcm)    DB=/home/j/.openclaw/lcm.db ;;
  main)   DB=/home/j/.openclaw/state/openclaw.sqlite ;;
  *) echo "ERR: 未知库别名（ledger|tasks|lcm|main）" >&2; exit 2 ;;
esac
SQL="${2:-}"
[ -n "$SQL" ] || { echo "ERR: 缺少 SQL" >&2; exit 2; }
[ -f "$DB" ] || { echo "ERR: 库不存在 $DB" >&2; exit 3; }
if printf '%s' "$SQL" | grep -qiE '\b(insert|update|delete|drop|alter|create|attach|detach|vacuum|reindex|replace|truncate)\b'; then
  echo "ERR: 只允许只读查询（SELECT/WITH/EXPLAIN）" >&2; exit 4
fi
if printf '%s' "$SQL" | grep -qiE '^[[:space:]]*pragma' ; then
  echo "ERR: 禁止 PRAGMA" >&2; exit 4
fi
DBPATH="$DB" SQLTEXT="$SQL" python3 - <<'PY'
import os, sqlite3, sys
db = os.environ["DBPATH"]; sql = os.environ["SQLTEXT"]
try:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=3.0)
except Exception as e:
    print("ERR: 打开失败:", e); sys.exit(5)
try:
    cur = con.execute(sql)
    rows = cur.fetchmany(200)
    if cur.description:
        print(" | ".join(d[0] for d in cur.description))
    for r in rows:
        print(" | ".join("" if v is None else str(v) for v in r))
    if len(rows) == 200:
        print("... (最多返回 200 行)")
except Exception as e:
    print("ERR: 查询失败:", e); sys.exit(6)
finally:
    con.close()
PY
exit $?
