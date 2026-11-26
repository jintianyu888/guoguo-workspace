#!/bin/bash
# gw-start-guard.sh —— 网关启动护栏（2026-11-26 立，事故 S0051 根治）
# 事故：旧进程仍持有 state 库时又启动第二个实例，新实例重建了 -wal（inode 变化），
#       11.10 的 WAL 身份校验判定 sidecar identity mismatch → FATAL 自杀 + 库页损坏。
# 规则：端口 18789 只要还有人 LISTEN，就绝不再拉第二个实例；要换必须走 restart-gateway.sh（先停后起）。
set -uo pipefail
export PATH=/usr/bin:/bin:/home/j/.npm-global/bin
PORT=18789
LOG=/home/j/.openclaw/workspace/state/work/gw-start-guard.log
say(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }

# 2026-11-26 顾问建议：端口只是辅助判据。真正防双开靠 (1) 启动互斥锁 (2) state 库写锁探测
LOCK=/home/j/.openclaw/state/.gw-start.lock
exec 9>"$LOCK" || { say "SKIP 拿不到锁文件 $LOCK"; exit 0; }
if ! flock -n 9; then
  say "SKIP 另一个启动流程正在进行（flock 被占用），拒绝并发启动"
  exit 0
fi
DB=/home/j/.openclaw/state/openclaw.sqlite
if [ -f "$DB" ]; then
  python3 - "$DB" <<'PY' 2>/dev/null
import sqlite3, sys
c = sqlite3.connect(sys.argv[1], timeout=0.5, isolation_level=None)
c.execute("PRAGMA busy_timeout=500")
c.execute("BEGIN IMMEDIATE")
c.execute("ROLLBACK")
c.close()
PY
  if [ $? -ne 0 ]; then
    say "SKIP state 库写锁被占用（另有进程正在写库），拒绝启动第二实例"
    exit 0
  fi
fi
BOUND=$(ss -ltn 2>/dev/null | awk -v p=":$PORT" '$4 ~ p"$" {print $4}' | head -1)
if [ -n "$BOUND" ]; then
  PID=$(ss -ltnp 2>/dev/null | grep ":$PORT " | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2)
  UNITPID=$(systemctl --user show -p MainPID --value openclaw-gateway 2>/dev/null)
  [ -z "$PID" ] && PID=?
  [ -z "$UNITPID" ] && UNITPID=0
  say "SKIP 端口 $PORT 已被 pid=$PID 占用（unit MainPID=$UNITPID），拒绝启动第二实例"
  if [ "$PID" != "0" ] && [ "$PID" != "?" ] && [ "$PID" != "$UNITPID" ] && [ "$UNITPID" = "0" ]; then
    say "WARN 网关在跑但不由 systemd 托管（stray pid=$PID）"
    bash /home/j/.openclaw/workspace/tools/notify.sh "【网关护栏】检测到网关 pid=$PID 未被 systemd 托管，已拒绝另起实例；请走 restart-gateway.sh 收编" >/dev/null 2>&1 || true
  fi
  exit 0
fi

say "端口空闲 → 通过 systemd 拉起（唯一托管路径）"
systemctl --user reset-failed openclaw-gateway 2>/dev/null || true
timeout 200 systemctl --user start openclaw-gateway >> "$LOG" 2>&1 || true
H=000
for i in $(seq 1 30); do
  sleep 4
  H=$(timeout 6 curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health" 2>/dev/null)
  [ "$H" = "200" ] && { say "启动成功 health=200"; exit 0; }
done
say "启动后 health 未就绪（最后一次=$H）"
exit 1
