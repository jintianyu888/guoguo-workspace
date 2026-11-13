#!/usr/bin/env bash
# 一次性：按主公 11-13 13:30 令，串行补跑原本用了 v4-pro 的 8 个任务（现为 zai/glm-5.3）
set -u
export PATH="$HOME/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
OC_BIN="$HOME/.npm-global/bin/openclaw"
[ -x "$OC_BIN" ] || OC_BIN=$(command -v openclaw)
W=/home/j/.openclaw/workspace
LOG=$W/state/work/run8-$(date +%Y%m%d-%H%M).log
ids=(
 ed4c9481-a255-495d-b856-77620658bd5e:告警双审修正
 7343f9f0-c9e9-496b-9b6d-743bbadc153a:果果助手每日双审
 564aeb60-60c4-4e9f-92cb-654c4f579d4a:周计划
 2fd10b3c-1882-4789-8ec1-3f1f7d41bba4:每周记忆配置体检
 330261ca-5dcf-42fc-b2a1-c625a5cf4f69:安装包升级巡检
 6ec8ec62-442a-4372-a146-05300d0da962:恢复文档审查
 935c9c9e-a99c-480c-bb4f-e53b0389c7df:月结
 aeeb49c3-471b-4474-b2e1-dd2883fc7394:年结
)
echo "START $(date -Is)" >> "$LOG"
for item in "${ids[@]}"; do
  id=${item%%:*}; nm=${item#*:}
  echo "== $nm ($id) begin $(date +%T)" >> "$LOG"
  timeout 900 "$OC_BIN" cron run "$id" --json >> "$LOG" 2>&1
  rc=$?
  echo "== $nm end rc=$rc $(date +%T)" >> "$LOG"
  sleep 20
done
echo "ALL_DONE $(date -Is)" >> "$LOG"
bash "$W/tools/notify.sh" "【补跑完成】8 个任务已串行跑完（结果见 $LOG）" >/dev/null 2>&1 || true
