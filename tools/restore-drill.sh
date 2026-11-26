#!/bin/bash
# restore-drill.sh —— 恢复演练：把最新快照还原到临时目录并验完整性（零 token）
set -uo pipefail
W=/home/j/.openclaw/workspace
LOCAL=/home/j/.openclaw/state/backups
TMPD=/tmp/drill-$$
mkdir -p "$TMPD"
SNAP=$(ls -1t "$LOCAL"/openclaw-*.sqlite 2>/dev/null | head -1)
if [ -z "$SNAP" ]; then echo "✗ 无快照可演练"; exit 1; fi
T0=$(date +%s%3N)
python3 - "$SNAP" "$TMPD" <<'PY'
import sqlite3, sys, os, shutil
snap, tmpd = sys.argv[1], sys.argv[2]
dst = os.path.join(tmpd, "drill.sqlite")
shutil.copy2(snap, dst)
c = sqlite3.connect(dst)
ic = c.execute("pragma integrity_check").fetchone()[0]
a = c.execute("select count(*) from audit_events").fetchone()[0]
c.close()
live = sqlite3.connect("file:/home/j/.openclaw/state/openclaw.sqlite?mode=ro", uri=True)
la = live.execute("select count(*) from audit_events").fetchone()[0]
live.close()
print("drill_integrity=%s" % ic)
print("audit_snapshot=%d audit_live=%d diff=%d" % (a, la, la - a))
PY
rc=$?
T1=$(date +%s%3N)
MS=$((T1-T0))
echo "耗时 $MS ms 快照=$(basename "$SNAP")"
rm -rf "$TMPD"
[ "$rc" -eq 0 ] || exit 1
echo "DRILL_OK $MS ms"
