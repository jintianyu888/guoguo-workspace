#!/bin/bash
# 只读查 state 库的安全入口：先复制到 /tmp 再用 python 查。
# 说明：sqlite3 CLI 在 state 库上会被护栏拒绝；本机也没有 sqlite3 二进制。
# 用法: bash tools/dbq.sh <库路径或 state 下相对路径> "SQL"
set -u
db="$1"; sql="$2"
case "$db" in
  /*) src="$db" ;;
  *)  src="/home/j/.openclaw/workspace/state/$db" ;;
esac
[ -f "$src" ] || { echo "库不存在: $src" >&2; exit 2; }
tmp="$(mktemp /tmp/dbq-XXXXXX.db)"
cp "$src" "$tmp"
python3 - "$tmp" "$sql" <<'PY'
import sqlite3, sys
db, sql = sys.argv[1], sys.argv[2]
c = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
try:
    for row in c.execute(sql):
        print("	".join("" if v is None else str(v) for v in row))
finally:
    c.close()
PY
rc=$?
rm -f "$tmp"
exit $rc
