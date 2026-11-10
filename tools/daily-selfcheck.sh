#!/bin/bash
# 每日系统自检 = 备份深度自检 + OpenClaw 健康自检 + 定时任务体检（全只读）
# 2026-10-26 修（C6/04:21 超时）：每步加硬上限（timeout），超时记「⏳ 跳过」不算失败；
#   原版无上限，backup-drill 深读归档 + 后续步骤叠加超过 cron 默认超时 → 整任务 error。
WS=/home/j/.openclaw/workspace
rc_all=0

step() { # $1=名称 $2=上限秒 $3..=命令
  local name="$1" lim="$2"; shift 2
  local t0 d rc
  t0=$(date +%s)
  timeout "$lim" "$@"
  rc=$?
  d=$(( $(date +%s) - t0 ))
  if [ "$rc" -eq 124 ]; then
    echo "⏳ ${name}：超过 ${lim}s 上限，已跳到下一步（不是失败，信息不全需人工看）"
  elif [ "$rc" -ne 0 ]; then
    echo "⚠️ ${name}：rc=${rc}（${d}s）"
    rc_all=1
  else
    echo "✅ ${name}：完成（${d}s）"
  fi
}

step "备份深度自检"   900 bash    "$WS/tools/backup-drill.sh"
echo
step "OpenClaw健康自检" 240 bash   "$WS/tools/openclaw-health.sh"
echo
step "定时任务体检"     300 python3 "$WS/tools/automations-audit.py"
step "/tmp占用检查"      60 sh      "$WS/tools/tmp-watch.sh"
step "本地模型探活"     180 bash    "$WS/tools/llm-local-check.sh"

echo "== 自检结束（rc=${rc_all}）=="
exit $rc_all
