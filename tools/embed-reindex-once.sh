#!/usr/bin/env bash
# embed-reindex-once.sh — 停网关 → 用 A 机 ollama 全量重建语义索引 → 启动网关（2026-11-07 21:30 主公令）
set -u
LOG=/home/j/.openclaw/workspace/state/work/embed-reindex-$(date +%Y%m%d-%H%M).log
exec >>"$LOG" 2>&1
echo "== $(date '+%F %T') 开始：嵌入 provider=ollama-a"

# 1) 暂停看门狗，避免它在维护中被拉起来
bash /home/j/.openclaw/workspace/tools/maintenance.sh start 20 "语义索引重建（停网关）"

# 2) 停网关
systemctl --user stop openclaw-gateway.service
for i in $(seq 1 60); do
  ss -ltn 2>/dev/null | grep -q ':18789' || break
  sleep 1
done
echo "网关已停（等待 $i 秒）"

# 3) 全量重建索引
cd /home/j/.openclaw
OB=/home/j/.npm-global/bin/openclaw
[ -x "$OB" ] || OB=$(command -v openclaw)
echo "用二进制: $OB"
timeout 1800 "$OB" memory index --agent main --force
rc=$?
echo "index rc=$rc"

# 4) 起网关并验证
systemctl --user start openclaw-gateway.service
health=000
for i in $(seq 1 45); do
  sleep 2
  health=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:18789/health)
  [ "$health" = "200" ] && break
done
echo "health=$health"
bash /home/j/.openclaw/workspace/tools/maintenance.sh stop

# 5) 回报
msg="语义记忆重建完成：嵌入已切 A 机(11435)，index rc=$rc，网关 health=$health，日志 $LOG"
/home/j/.openclaw/workspace/tools/notify.sh "$msg" 2>/dev/null || echo "$msg" >>/home/j/.openclaw/workspace/state/work/embed-reindex-notify-failed.txt
echo "== $(date '+%F %T') 结束"
