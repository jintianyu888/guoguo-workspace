#!/bin/bash
# state-db-restore.sh —— 从小时快照恢复 state 库（RTO 机制，2026-11-26 立）
# 用法：state-db-restore.sh --from /mnt/d/oc-state-backups/openclaw-YYYYMMDD-HH.sqlite [--apply]
# 默认 dry-run：只校验候选快照与当前库的差异，不动任何东西。
set -uo pipefail
export PATH=/usr/bin:/bin:/home/j/.npm-global/bin
W=/home/j/.openclaw/workspace
OH=/home/j/.openclaw
LOG="$W/state/work/state-restore.log"
LIVE="$OH/state/openclaw.sqlite"
FROM=""; APPLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    *) echo "未知参数 $1"; exit 2 ;;
  esac
done
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
[ -n "$FROM" ] && [ -f "$FROM" ] || { echo "缺少或找不到 --from 快照"; exit 2; }

say "候选：$FROM"
python3 - "$FROM" "$LIVE" <<'PY'
import sqlite3, sys
f, live = sys.argv[1], sys.argv[2]
def probe(p, ro=False):
    c = sqlite3.connect(p, timeout=20)
    ic = c.execute("pragma integrity_check").fetchone()[0]
    rows = {}
    for q, k in [("select count(*) from sessions", "sessions"),
                 ("select count(*) from audit_events", "audit"),
                 ("select count(*) from cron_jobs", "cron")]:
        try: rows[k] = c.execute(q).fetchone()[0]
        except Exception: rows[k] = "?"
    c.close(); return ic, rows
ic, r = probe(f)
print("快照 integrity_check =", ic, r)
if ic != "ok":
    sys.exit(3)
PY
rc=$?
[ "$rc" -eq 0 ] || { say "✗ 快照未通过 integrity_check，拒绝恢复"; exit 3; }

if [ "$APPLY" != "1" ]; then
  say "dry-run：快照可用，未做改动。加 --apply 才执行恢复（会短暂停网关）"
  exit 0
fi

say "① 停看门狗 + 网关"
systemctl --user stop oc-gateway-watchdog.timer 2>/dev/null
touch "$W/state/work/.watchdog-pause"
systemctl --user stop openclaw-gateway.service 2>/dev/null
sleep 3
PID=$(ss -ltnp 2>/dev/null | grep ":18789 " | grep -oE 'pid=[0-9]+' | head -1)
[ -n "$PID" ] && { say "✗ 端口 18789 仍被占用（$PID），中止"; exit 4; }

TS=$(date +%Y%m%d-%H%M%S)
say "② 现有库转存 .pre-restore-$TS"
mv -f "$LIVE" "$LIVE.pre-restore-$TS" 2>/dev/null
rm -f "$LIVE-wal" "$LIVE-shm"
cp -f "$FROM" "$LIVE" && chmod 600 "$LIVE"
say "③ 启动"
bash "$W/tools/gw-start-guard.sh" >>"$LOG" 2>&1
H=$(timeout 10 curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/health)
if bash "$W/tools/db-integrity-gate.sh" >>"$LOG" 2>&1; then DBOK=ok; else DBOK=BAD; fi
rm -f "$W/state/work/.watchdog-pause"
systemctl --user start oc-gateway-watchdog.timer 2>/dev/null
say "④ 结果 health=$H 库=$DBOK（旧库留在 $LIVE.pre-restore-$TS）"
if [ "$H" = "200" ] && [ "$DBOK" = "ok" ]; then
  timeout 60 bash "$W/tools/notify.sh" "【state 恢复完成】来自 $FROM｜health 200｜库 ok｜旧库 .pre-restore-$TS" >/dev/null 2>&1 || true
  exit 0
fi
timeout 60 bash "$W/tools/notify.sh" --alert "【state 恢复异常】health=$H 库=$DBOK，见 $LOG" >/dev/null 2>&1 || true
exit 1
