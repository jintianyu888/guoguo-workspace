#!/usr/bin/env bash
# host-insights-10m.sh —— 10 分钟主机洞察合体（2026-10-01 任务整合 / 任务四）
# 原 2 个独立 every-10min 任务合并为 1 条：
#   host-peak-sampler(15302004) / footer-collect(1540163e)
# 安全设计：每项 timeout 60s，单项失败不影响其他；日志滚动 3000 行。
# 回滚：重新 enable 上述 2 条，disable 本条（见 state/tasks-integration-20261001.md）
set -u
W=/home/j/.openclaw/workspace
LOG="$W/state/host-insights-10m.log"
mkdir -p "$W/state"

run() {
  local name="$1" script="$2" out rc
  out=$(timeout 60 bash "$script" 2>&1); rc=$?
  [ -n "$out" ] && printf '%s\n' "$out"
  printf '%s | %-18s | rc=%-3s | %s\n' "$(date '+%F %T')" "$name" "$rc" "$(printf '%s' "$out" | head -c 160 | tr '\n' ' ')" >> "$LOG"
  return 0
}

# 2026-11-02：采样职责已迁至 systemd 单元 host-peak-sampler.timer（原 openclaw cron
# 15302004 已停用），本条不再重复调用，否则每 10 分钟会产生两份重复采样行。
# run host-peak-sampler "$W/tools/host-peak-sample.sh"
run footer-collect    "$W/tools/footer-collect.sh"

if [ -f "$LOG" ]; then tail -n 3000 "$LOG" > "$LOG.rot" && mv "$LOG.rot" "$LOG"; fi
exit 0
