#!/usr/bin/env bash
# llm-failover.sh - 大模型卡死 → 自动切换 key（默认切到「主公key」），零 token 定时跑
W=/home/j/.openclaw/workspace; ST=$W/state; mkdir -p "$ST"
LOG=$ST/llm-failover.log; ALERT=$ST/llm-alert.txt; TS=$(date "+%F %T")
CFG=/home/j/.openclaw/openclaw.json

# 1) 探活：极小调用（几十 token）
R=$(timeout 45 openclaw infer model run --agent main --gateway --model deepseek/deepseek-flash --prompt "ok" 2>&1 | tail -4)

# 2026-09-27 修正：配置告警行（如 "plugin disabled in config"）曾造成误判 → 先剔除告警行，再匹配真正的失败
R2=$(printf '%s\n' "$R" | grep -viE "warnings?:|disabled in config|plugin .*disabled")
if echo "$R2" | grep -qiE "\berror\b|401|402|timed out|unavailable|failed to|no provider"; then
  CUR=$(python3 -c "import json;d=json.load(open('$CFG'));print((d['models']['providers']['deepseek'].get('apiKey') or {}).get('id',''))" 2>/dev/null)
  echo "$TS FAIL cur=$CUR :: $(echo "$R" | head -1)" >> "$LOG"
  if [ "$CUR" != "deepseek:manual" ]; then
    timeout 60 openclaw config set models.providers.deepseek.apiKey '"deepseek:manual"' --strict-json >> "$LOG" 2>&1
    echo "$TS SWITCH $CUR -> deepseek:manual(在用的唯一key)" >> "$LOG"
    echo "🔴【自动切换】大模型卡死 → 已切到在用的 deepseek:manual｜原 key: $CUR｜$TS" > "$ALERT"
  else
    echo "$TS deepseek:manual 也不通，无可切换的备用 deepseek key" >> "$LOG"
    echo "🔴【切换失败】deepseek:manual 不通且已无备用 deepseek key（$TS）→ 建议：临时用 ollama 兜底或新录一把 key" > "$ALERT"
  fi
else
  echo "$TS OK" >> "$LOG"
  [ -f "$ALERT" ] && echo "$TS RECOVERED 已恢复，清除告警" >> "$LOG" && rm -f "$ALERT"
fi
tail -n 800 "$LOG" > "$LOG.t" 2>/dev/null && mv "$LOG.t" "$LOG"
# 有告警则输出到 stdout（供定时任务 announce 直推飞书）
if [ -f "$ALERT" ]; then cat "$ALERT"; fi
exit 0
