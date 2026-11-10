#!/usr/bin/env bash
# deadletter-hygiene.sh v1.3 — 死信日清 + 阈值告警
# 2026-11-04 建立；v1.1 加固误删边界与导出校验；v1.2 按 qianwen+kimi 双审意见再加固；v1.3 墓碑判定改为解析 entry_json 白名单 key：
#   - 墓碑判定改为"白名单列以外的列必须全空"（新增列有值时自动不删）
#   - 导出：tmp+fsync → 原子 rename → fsync 父目录 → 回读比对 sha256（不是只比行数）
#   - 删除：按事务内选出的 (queue_name,id) 精确删除，并核对删除行数，不等则回滚
#   - 任一步失败 exit 3，并对外告警（不再静默）
# 回滚：python3 tools/deadletter-restore.py <export.jsonl> [--dry-run]
set -uo pipefail
WS="/home/j/.openclaw/workspace"
DB="/home/j/.openclaw/state/openclaw.sqlite"
LOG="$WS/state/deadletter-hygiene.log"
EDIR="$WS/state/work/deadletter-purged"
ALERT_MARK="$WS/state/deadletter-alert.flag"
TS="$(date '+%F %T')"
STAMP="$(date '+%Y%m%d-%H%M%S')"
KEEP_DAYS="${1:-1}"
ALERT_N="${2:-30}"
mkdir -p "$(dirname "$LOG")" "$EDIR"

OUT=$(python3 - "$DB" "$EDIR" "$KEEP_DAYS" "$TS" "$STAMP" <<'PY'
import hashlib, json, os, sqlite3, sys, time
db, edir, days, ts, stamp = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4], sys.argv[5]
cutoff = int((time.time() - days*86400) * 1000)
# 墓碑判定（v1.3）：entry_json 只含 id/时间/重试/保留策略这类记账字段，不含任何 payload。
# 允许出现的 key（出现其它 key 即视为有载荷，不删）
TOMB_KEYS = {"id","enqueuedAt","retryCount","failedAt","completionRetention","recoveryState",
             "attemptCount","lastAttemptAt","enqueued_at","failed_at"}
c = sqlite3.connect(db, isolation_level=None, timeout=30)
c.execute("pragma busy_timeout=30000")
cols = [r[1] for r in c.execute("pragma table_info(delivery_queue_entries)")]
tcol = "failed_at" if "failed_at" in cols else ("enqueued_at" if "enqueued_at" in cols else "updated_at")
idc = "coalesce(id,'')"
sql_where = (f"status='failed' and coalesce(target,'')='' and coalesce(channel,'')='' "
             f"and coalesce(session_key,'')='' and coalesce(last_error,'')='' "
             f"and coalesce({tcol}, updated_at) < ?")
def is_tomb(row):
    d = dict(zip(cols, row))
    raw = d.get("entry_json") or ""
    if not raw:
        return (d.get("recovery_state") in (None, "completed_permanent"))
    try:
        j = json.loads(raw)
    except Exception:
        return False
    if not isinstance(j, dict):
        return False
    return set(j.keys()) <= TOMB_KEYS
def fail(msg):
    try: c.execute("rollback")
    except Exception: pass
    print(json.dumps({"error": msg, "purged": 0})); sys.exit(3)
try:
    c.execute("begin immediate")
    cand = c.execute(f"select * from delivery_queue_entries where {sql_where}", (cutoff,)).fetchall()
    rows = [r for r in cand if is_tomb(r)]
    n = len(rows)
    if n:
        payload = json.dumps({"purged_at": ts, "cutoff_ms": cutoff, "columns": cols, "rows": rows},
                             ensure_ascii=False, sort_keys=True).encode()
        digest = hashlib.sha256(payload).hexdigest()
        final = os.path.join(edir, f"purged-{stamp}.jsonl")
        tmp = final + ".tmp"
        with open(tmp, "wb") as f:
            f.write(payload + b"\n"); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, final)
        dfd = os.open(edir, os.O_RDONLY); os.fsync(dfd); os.close(dfd)
        back = json.loads(open(final, "rb").read().decode())
        if hashlib.sha256(json.dumps(back, ensure_ascii=False, sort_keys=True).encode()).hexdigest() != digest:
            fail("export hash mismatch")
        if len(back.get("rows", [])) != n:
            fail("export row count mismatch")
        cur = c.executemany("delete from delivery_queue_entries where queue_name=? and id=?",
                            [(r[0], r[1]) for r in rows])
        if cur.rowcount not in (-1, n):
            fail(f"delete rowcount {cur.rowcount} != {n}")
        left = sum(1 for r in c.execute(f"select * from delivery_queue_entries where {sql_where}", (cutoff,)).fetchall() if is_tomb(r))
        if left:
            fail(f"{left} tombstone rows still present after delete")
        c.execute("commit")
        out_export = final
    else:
        c.execute("commit"); out_export = ""
    day_ago = int((time.time() - 86400) * 1000)
    new24 = c.execute(f"select count(*) from delivery_queue_entries where status='failed' and coalesce({tcol}, updated_at) >= ?", (day_ago,)).fetchone()[0]
    rem = c.execute("select count(*) from delivery_queue_entries where status='failed'").fetchone()[0]
    print(json.dumps({"purged": n, "failed_24h": new24, "failed_remaining": rem, "time_col": tcol, "export": out_export}))
except SystemExit:
    raise
except Exception as e:
    fail(str(e))
finally:
    try: c.close()
    except Exception: pass
PY
)
RC=$?
echo "[$TS] rc=$RC $OUT" >> "$LOG"
echo "$OUT"

if [ "$RC" -ne 0 ]; then
  timeout 60 bash "$WS/tools/notify.sh" --alert "告警：死信日清失败 rc=$RC —— $OUT" >/dev/null 2>&1 || true
  exit 3
fi

N24=$(python3 -c "import json,sys;print(json.loads(sys.argv[1]).get('failed_24h',0))" "$OUT" 2>/dev/null || echo 0)
TODAY=$(date +%F)
if [ "${N24:-0}" -gt "${ALERT_N:-30}" ] && [ "$(cat "$ALERT_MARK" 2>/dev/null || true)" != "$TODAY" ]; then
  if timeout 60 bash "$WS/tools/notify.sh" --alert "告警：投递死信 24h 新增 ${N24} 条（阈值 ${ALERT_N}）。多为飞书回复 id 失效 99992354；明细 bash tools/alert-digest.sh --hours 24" >/dev/null 2>&1; then
    echo "$TODAY" > "$ALERT_MARK"
  else
    echo "[$TS] notify failed" >> "$LOG"
  fi
fi
exit 0
