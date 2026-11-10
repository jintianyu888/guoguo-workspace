#!/bin/bash
# backup-wait-idle.sh —— 备份前「等空闲」守卫（2026-10-02 主公令）
# 规则：若有其他备份/重活在跑，等它跑完再开始；并用 flock 串行化所有备份。
set -u
W=/home/j/.openclaw/workspace
LOCK=$W/state/work/.backup.lock
MAXWAIT=1200
exec 9>"$LOCK"
if ! flock -w "$MAXWAIT" 9; then
  # 2026-10-26 修：等锁超时是"按设计跳过"，不是失败；原来 exit 3 让 cron 记 error（T1重点备份 10-26 00:15 即此）
  echo "[wait-idle] 等锁超时（${MAXWAIT}s），放弃本次（调用方：$(basename "$0")）— 记为跳过，非失败"
  timeout 45 bash "$W/tools/notify.sh" "⏳ 备份跳过：$(basename "$0") 等锁超时 $((MAXWAIT/60)) 分钟没轮到（是跳过，不是失败）" >/dev/null 2>&1 || true
  exit 0
fi
waited=0
while :; do
  # 2026-10-02 修（cron 报 error 的真根因）：pgrep -c 无匹配时「先打印 0、再返回非零」，
  # 旧的 `|| echo 0` 会再追加一个 0 → 变量成两行「0」→ $(( )) 报 Illegal number → exit 2。
  # 正确写法：直接用 -c 的输出，空则补 0。
  busy=$(pgrep -x rsync -c 2>/dev/null); busy=${busy:-0}
  _t=$(pgrep -x tar -c 2>/dev/null); busy=$((busy + ${_t:-0}))
  _b=$(pgrep -f batch-extract -c 2>/dev/null); busy=$((busy + ${_b:-0}))
  [ "$busy" -eq 0 ] && break
  [ "$waited" -ge "$MAXWAIT" ] && { echo '[wait-idle] 重活未结束，已等 $((MAXWAIT/60)) 分钟，超时放行（2026-10-25 主公批：不再无限等）'; timeout 30 bash "$W/tools/notify.sh" "⏳ 备份不再等：其它重活 ${MAXWAIT}s 内没结束，已放行开跑" >/dev/null 2>&1 || true; break; }
  sleep 20; waited=$((waited+20))
done
echo "[wait-idle] 就绪（等了 $waited s，锁已持有）"