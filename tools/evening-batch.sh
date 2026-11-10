#!/bin/bash
# evening-batch.sh —— 18:05 半价窗批量执行（找活 + 清账 + 汇总）
# 设计：只做本地脚本，不烧云端；产出摘要发飞书。
set -uo pipefail
WS=/home/j/.openclaw/workspace
cd "$WS" || exit 2
DAY=$(date +%Y%m%d)
OUT="$WS/state/work/evening-batch-$DAY.md"
LOG="$WS/state/work/evening-batch.log"

echo "# 傍晚批次 $DAY $(date +%H:%M)" > "$OUT"
echo "" >> "$OUT"

echo "[1/4] 空转侦察" | tee -a "$LOG"
timeout 300 nice -n 19 ionice -c3 python3 tools/idle-scout.py >> "$OUT" 2>>"$LOG"

echo "[2/4] 交付验收" | tee -a "$LOG"
timeout 300 nice -n 19 ionice -c3 python3 tools/steward-acceptance.py >> "$OUT" 2>>"$LOG"

echo "[3/4] 待办汇总" | tee -a "$LOG"
python3 - "$OUT" <<'PY' >> "$LOG" 2>&1
import sqlite3, sys
out=sys.argv[1]
try:
    c=sqlite3.connect("/home/j/.openclaw/workspace/state/ledger/ledger.db")
    cur=c.cursor()
    cur.execute("SELECT status, COUNT(*) FROM tasks WHERE status IN ('pending','open','in_progress','quarantine','paused') GROUP BY status")
    rows=cur.fetchall()
    with open(out,"a",encoding="utf-8") as f:
        f.write("\n## 台账未完成\n")
        for s,n in rows:
            f.write("- %s: %d\n" % (s,n))
except Exception as e:
    print("ledger err", e)
PY

echo "[4/4] 账本审计" | tee -a "$LOG"
python3 tools/ledger-audit.py >> "$OUT" 2>>"$LOG"
ARC=$?
ALERT=0
if [ "$ARC" -ne 0 ]; then
  { echo ""; echo "## 账本审计未通过 rc=$ARC（0=通过 1=hard缺口 2=环境异常）"; } >> "$OUT"
  echo "ledger-audit FAIL rc=$ARC" >> "$LOG"
  ALERT=1
fi

MSG=$(head -c 600 "$OUT" | tr '\n' ' ')
if ! bash tools/notify.sh "傍晚批次 $DAY 完成
$(sed -n '1,12p' "$OUT")" >/dev/null 2>&1; then
  echo "notify FAILED" >> "$LOG"
  ALERT=1
fi
echo "done $(date +%H:%M) alert=$ALERT" >> "$LOG"
exit $ALERT
