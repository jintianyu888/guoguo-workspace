#!/bin/bash
# restore-drill.sh v3 — 备份恢复演练（2026-10-18 主公令：一三五 14:00 备份后执行）
# 检查：① 三端同名校验 ② 全流完整性 tar -tzf ③ 关键资产覆盖 ④ 真实抽取 lcm.db 做 integrity_check
# 只读：不删备份、不动生产数据；抽取物落 /home/j/restore-drill/，保留最近 3 次
set -uo pipefail
W=/home/j/.openclaw/workspace
LOG=$W/state/restore-drill.log
LEDGER=$W/state/restore-drill-ledger.jsonl
LOCK=$W/state/work/restore-drill.lock
DRILL=/home/j/restore-drill
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p "$W/state/work" "$DRILL"
exec 9>"$LOCK"
flock -n 9 || { echo "[$(date '+%F %T')] SKIP 已有演练在跑"; exit 0; }
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
ARCH=""; FF=""
for d in /mnt/d/openclaw-backups /mnt/e/openclaw-backups /mnt/h/openclaw-backups; do
  c=$(ls -t "$d"/*openclaw-backup.tar.gz 2>/dev/null | head -1)
  if [ -n "$c" ]; then ARCH="$d"; FF="$c"; break; fi
done
[ -z "$FF" ] && { say "❌ 找不到任何官方归档"; exit 1; }
BASE=$(basename "$FF"); SIZE=$(stat -c %s "$FF")
say "🔬 恢复演练开始 · 归档=$BASE · 大小=$SIZE · 来源=$ARCH"
FAIL=0; NOTE=()
for d in /mnt/d /mnt/e /mnt/h; do
  o="$d/openclaw-backups/$BASE"
  if [ -f "$o" ]; then s2=$(stat -c %s "$o"); if [ "$s2" = "$SIZE" ]; then NOTE+=("$d同名校验✅"); else NOTE+=("$d同名校验❌"); FAIL=1; fi; else NOTE+=("$d无副本⚠️"); fi
done
LT=$(mktemp "$W/state/tmp/rd-list.XXXXXX")
T0=$(date +%s)
if tar -tzf "$FF" > "$LT" 2>"$LT.err"; then N=$(wc -l < "$LT"); NOTE+=("全流校验✅${N}条"); else NOTE+=("全流校验❌"); FAIL=1; fi
T1=$(date +%s); SEC_LIST=$((T1-T0))
chk(){ if grep -qE "$2" "$LT"; then NOTE+=("$1✅"); else NOTE+=("$1❌"); FAIL=1; fi; }
chk 'openclaw.json' 'payload/posix/home/j/\.openclaw/openclaw\.json$'
chk 'state主库' 'payload/posix/home/j/\.openclaw/state/openclaw\.sqlite$'
chk 'lcm.db' 'payload/posix/home/j/\.openclaw/.+lcm\.db$'
AG=$(grep -cE 'payload/posix/home/j/\.openclaw/agents/[^/]+/agent/openclaw-agent\.sqlite$' "$LT" || true)
WS=$(grep -cE 'payload/posix/home/j/openclaw-workspaces/[^/]+/' "$LT" || true)
NOTE+=("管家库${AG}个"); if [ "${WS:-0}" -ge 1 ] 2>/dev/null; then NOTE+=("工作区${WS}条"); else NOTE+=("工作区缺失❌"); FAIL=1; fi
OUT=$DRILL/$TS; mkdir -p "$OUT"; SEC_EX=0
LCM=$(grep -E 'payload/posix/home/j/\.openclaw/.+lcm\.db$' "$LT" | head -1)
if [ -n "$LCM" ]; then
  T2=$(date +%s)
  if tar -xzf "$FF" -C "$OUT" "$LCM" 2>/dev/null; then
    RES=$(python3 - "$OUT/$LCM" <<'PY'
import sqlite3,sys
try:
    c=sqlite3.connect("file:"+sys.argv[1]+"?mode=ro",uri=True)
    r=c.execute("pragma integrity_check").fetchone()[0]
    n=c.execute("select count(*) from sqlite_master where type='table'").fetchone()[0]
    print(str(r)+"|"+str(n))
except Exception as e:
    print("ERROR "+str(e)+"|0")
PY
)
    IC=${RES%%|*}; TB=${RES##*|}
    if [ "$IC" = "ok" ]; then NOTE+=("lcm.db抽取+integrity✅${TB}表"); else NOTE+=("lcm.db integrity❌"); FAIL=1; fi
  else NOTE+=("lcm.db抽取❌"); FAIL=1; fi
  T3=$(date +%s); SEC_EX=$((T3-T2))
else NOTE+=("lcm.db未找到❌"); FAIL=1; fi
ls -1dt "$DRILL"/*/ 2>/dev/null | tail -n +4 | xargs -r rm -rf
rm -f "$LT" "$LT.err"
NOW=$(date +%s); DUR=$((NOW-T0))
if [ "$FAIL" -eq 0 ]; then RESULT="✅通过"; RC=0; else RESULT="❌失败"; RC=1; fi
DETAIL=$(printf "%s｜" "${NOTE[@]}")
say "$RESULT · $BASE · 列表${SEC_LIST}s 抽取${SEC_EX}s 总${DUR}s"
say "明细：$DETAIL"
printf '{"ts":"%s","archive":"%s","size":%s,"result":"%s","fail":%s,"list_sec":%s,"extract_sec":%s,"detail":"%s"}\n' \
  "$(date '+%F %T')" "$BASE" "$SIZE" "$RESULT" "$FAIL" "$SEC_LIST" "$SEC_EX" "$DETAIL" >> "$LEDGER"
if [ "$RC" -eq 0 ]; then bash "$W/tools/notify.sh" "🧪 恢复演练通过｜$BASE｜用时${DUR}s｜$DETAIL" >/dev/null 2>&1;
else bash "$W/tools/notify.sh" "🚨 恢复演练失败｜$BASE｜用时${DUR}s｜$DETAIL" >/dev/null 2>&1; fi
exit $RC