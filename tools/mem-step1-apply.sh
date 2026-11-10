#!/usr/bin/env bash
# mem-step1-apply.sh —— 内存调参 step1 生效+验收（网关进程外运行）
# 由 systemd-run 定时触发：重启网关 → 等就绪 → 回读堆帽/cgroup/健康 → 记日志+通知
set -u
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace
LOG=$W/state/work/mem-step1-verify.log
: > "$LOG"
log(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

log "=== step1 生效开始（重启前基线）"
log "cgroup high/max: $(systemctl --user show openclaw-gateway -p MemoryHigh -p MemoryMax --value | tr '\n' ' ')"
log "RSS: $(ps -o rss= -p $(pgrep -f 'dist/index.js gateway' | head -1) 2>/dev/null | awk '{printf \"%.2f GiB\", $1/1048576}')"

bash "$W/tools/restart-gateway.sh" --reason "内存调参 step1（堆帽 6144）" >>"$LOG" 2>&1
log "restart 提交 rc=$?"

for i in $(seq 1 40); do
  H=$(timeout 5 curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/health 2>/dev/null)
  [ "$H" = "200" ] && break
  sleep 5
done
PID=$(pgrep -f 'dist/index.js gateway' | head -1)
log "=== 验收"
log "health=$(timeout 5 curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/health)"
log "pid=${PID:-无}"
log "argv=$(ps -o args= -p ${PID:-0} 2>/dev/null)"
log "cgroup high/max=$(systemctl --user show openclaw-gateway -p MemoryHigh -p MemoryMax --value | tr '\n' ' ')"
log "RSS=$(ps -o rss= -p ${PID:-0} 2>/dev/null | awk '{printf \"%.2f GiB\", $1/1048576}')"
log "NRestarts=$(systemctl --user show openclaw-gateway -p NRestarts --value)"

if ps -o args= -p "${PID:-0}" 2>/dev/null | grep -q "max-old-space-size=6144"; then
  log "结果: 堆帽 6144 已生效"
  timeout 40 bash "$W/tools/notify.sh" "内存调参step1生效：堆帽6144，cgroup 7G/10G，网关已恢复" >/dev/null 2>&1 || true
else
  log "结果: 堆帽未生效（argv 里没有 6144）"
  timeout 40 bash "$W/tools/notify.sh" --alert "内存调参step1：堆帽未生效，请查 $LOG" >/dev/null 2>&1 || true
fi
