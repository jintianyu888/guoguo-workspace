#!/usr/bin/env bash
# backup-quiet-guard.sh v2.1 —— 三条自愈路径（2026-10-20 v4-pro+kimi 双模评审后补强）
# 路径1  ：账本有暂停残留但状态文件不在（pause 中途被打断）→ 立即按账本自愈恢复
# 路径1.5：账本有待恢复项且备份链进程已不在（pause 后 SIGKILL / resume 中途被杀）
#          → 立即恢复+告警。用「备份主进程在不在」区分正常静默与恢复中断，
#            正常备份期间（主进程在跑）绝不误恢复、不击穿静默。（评审共识必修项）
# 路径2  ：状态文件在，超 180 分钟未恢复 → 恢复并告警（兜底）
set -uo pipefail
WS=/home/j/.openclaw/workspace
STATE="$WS/state/backup-quiet/state.json"
LOG="$WS/state/work/backup-quiet-guard.log"
MARKER="$WS/state/work/backup-quiet-guard.last"
touch "$MARKER"   # 心跳：marker 的 mtime = 哨兵最近一次运行时间（哨兵存活可观测）

# 备份链是否仍在跑（匹配词刻意避开 backup-quiet-guard 自身，防 pgrep 误中）
backup_alive() {
  pgrep -f 'backup-quiet\.py (pause|resume)|backup-with-quiet\.sh|nas-push-archive|heartbeat-run' >/dev/null 2>&1
}

OUT=$(python3 "$WS/tools/backup-quiet.py" status 2>/dev/null || true)

# 路径1：中断残留自愈（不依赖状态文件）
if echo "$OUT" | grep -q "中断残留"; then
  R=$(python3 "$WS/tools/backup-quiet.py" resume 2>&1 || true)
  echo "[$(date '+%F %T')] 账本残留自愈: $R" >> "$LOG"
  bash "$WS/tools/notify.sh" "⚠️ 备份静默账本发现中断残留，已自动恢复定时任务：$R" >> "$LOG" 2>&1 || true
  exit 0
fi

# 路径1.5：有待恢复项且备份链进程已退出 → 立即自愈（消除原 180 分钟盲区）
if echo "$OUT" | grep -Eq '账本待恢复: [1-9]' && ! backup_alive; then
  R=$(python3 "$WS/tools/backup-quiet.py" resume 2>&1 || true)
  echo "[$(date '+%F %T')] 待恢复残留+备份进程已退出，自愈: $R" >> "$LOG"
  bash "$WS/tools/notify.sh" "⚠️ 备份静默有未恢复任务且备份进程已退出，已自动恢复：$R" >> "$LOG" 2>&1 || true
  exit 0
fi

# 路径2：超时恢复（兜底；备份卡死挂住时也兜）
[ -f "$STATE" ] || exit 0
AGE=$(python3 -c "import json,datetime;d=json.load(open('$STATE'));print(int((datetime.datetime.now()-datetime.datetime.fromisoformat(d['paused_at'])).total_seconds()/60))" 2>/dev/null || echo 0)
if [ "$AGE" -gt 180 ]; then
  python3 "$WS/tools/backup-quiet.py" resume >> "$LOG" 2>&1
  bash "$WS/tools/notify.sh" "⚠️ 备份静默已持续 ${AGE} 分钟，已自动恢复全部定时任务（备份可能异常退出）" >> "$LOG" 2>&1 || true
  echo "[$(date '+%F %T')] 超时 ${AGE} 分钟，已自动恢复" >> "$LOG"
fi
exit 0
