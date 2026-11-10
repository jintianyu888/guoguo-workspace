#!/usr/bin/env bash
# frequent-checks-5m.sh —— 5 分钟巡检合体（2026-10-01 任务整合 / 任务四）
# 原 4 个独立 every-5min 任务合并为 1 条：
#   self-monitor(5d4578d4) / llm-failover(63c9acf1) / 网关重启守望(82370297) / 回收站搬运完成通告(d0b7f7ba)
# 安全设计：
#   · 每项 timeout 60s —— 单项卡死不会拖垮其它项
#   · 单项失败不影响后续（不 set -e）
#   · 每次运行写一行到本地日志（零 token），日志滚动保留最后 3000 行
#   · 正常静默，有输出才 announce（与原任务一致）
# 回滚：重新 enable 上述 4 条，disable 本条即可（见 state/tasks-integration-20261001.md）
set -u
W=/home/j/.openclaw/workspace
LOG="$W/state/frequent-checks-5m.log"
mkdir -p "$W/state"

run() {
  local name="$1" script="$2" out rc
  out=$(timeout 60 bash "$script" 2>&1); rc=$?
  [ -n "$out" ] && printf '%s\n' "$out"
  printf '%s | %-14s | rc=%-3s | %s\n' "$(date '+%F %T')" "$name" "$rc" "$(printf '%s' "$out" | head -c 160 | tr '\n' ' ')" >> "$LOG"
  return 0
}

run self-monitor   "$W/tools/self-monitor.sh"
run llm-failover   "$W/tools/llm-failover.sh"
run gateway-watch  "$W/tools/gateway-watch.sh"
run trash-notice   "$W/tools/trash-done-notice.sh"

if [ -f "$LOG" ]; then tail -n 3000 "$LOG" > "$LOG.rot" && mv "$LOG.rot" "$LOG"; fi
exit 0

