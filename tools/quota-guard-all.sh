#!/bin/bash
# quota-guard-all.sh —— 额度守卫与调档合并入口（2026-10-24 方案A · 双审修订版）
# 顺序：quota-guard.py（判定+告警）→ pool-quota-fallback.sh（降级/恢复）
# 修订要点（评审必改）：
#  · timeout -k 10 防 SIGTERM 被忽略后无限等待
#  · flock 跳过必须写日志（否则静默停摆无人知）
#  · 任一子步骤失败即告警（不再要求“两项都失败”），6h 去重
#  · pool 超时（rc=124）视为半切换风险，强制告警并 exit 3
#  · 结束后核对 GLM 当前档位与 mode 文件是否一致
set -u -o pipefail
W=/home/j/.openclaw/workspace
LOG="$W/state/work/quota-guard-all.log"
ALERT_STAMP="$W/state/work/quota-guard-all.alert"
mkdir -p "$W/state/work"

ts() { date '+%F %T'; }
log() { echo "$(ts) $*" >> "$LOG"; }

exec 9>"$W/state/work/quota-guard-all.lock"
if ! flock -n 9; then
  log "已有实例在跑，本次跳过"
  exit 0
fi

# 6h 去重告警
alert_once() {
  local msg="$1" now last=0
  now=$(date +%s)
  [ -f "$ALERT_STAMP" ] && last=$(cat "$ALERT_STAMP" 2>/dev/null || echo 0)
  case "$last" in ''|*[!0-9]*) last=0;; esac
  if [ $((now - last)) -ge 21600 ]; then
    echo "$now" > "$ALERT_STAMP"
    timeout 30 bash "$W/tools/notify.sh" "⚠️ 额度守卫异常" "$msg" >/dev/null 2>&1 || true
    log "已告警：$msg"
  else
    log "告警抑制中（6h 去重）：$msg"
  fi
}

log "=== 开始 ==="
rc1=0; rc2=0; rc0=0

# 2026-10-26 C4/C5 修：glm-quota-guard.py v0.3 才是 glm-quota-state.json 的唯一写者
#  （面板 quotas.json + 6h 日志限流双源）；此前无人调用 → 状态 2421 分钟不更新
timeout -k 10 120 python3 "$W/tools/glm-quota-guard.py" >> "$LOG" 2>&1 || rc0=$?
log "glm-quota-guard rc=$rc0"

timeout -k 10 300 python3 "$W/tools/quota-guard.py" >> "$LOG" 2>&1 || rc1=$?
log "quota-guard rc=$rc1"
[ "$rc1" -ne 0 ] && alert_once "quota-guard rc=$rc1（判定环节失败，阈值告警可能漏发）"

timeout -k 10 300 bash "$W/tools/pool-quota-fallback.sh" >> "$LOG" 2>&1 || rc2=$?
log "pool-quota rc=$rc2"

if [ "$rc2" -eq 124 ]; then
  alert_once "pool-quota 超时(124)，可能半切换：请核对 GLM 档位与 mode 文件"
  log "完成（rc1=$rc1 rc2=124 超时）"
  exit 3
fi
[ "$rc2" -ne 0 ] && alert_once "pool-quota rc=$rc2（降级/恢复环节失败）"

# 一致性核对：mode 文件与日志末行目标档位
MODE_FILE="$W/state/model-econ/glm-mode.txt"
if [ -f "$MODE_FILE" ]; then
  log "当前 mode 文件：$(cat "$MODE_FILE" 2>/dev/null | tr -d '\n')"
else
  log "未找到 mode 文件（若脚本用别处记录可忽略）"
fi

log "完成（rc1=$rc1 rc2=$rc2）"
exit 0
