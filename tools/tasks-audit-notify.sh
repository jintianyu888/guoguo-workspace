#!/bin/bash
# tasks-audit-notify.sh — 每日台账保洁，仅在发现异常时告警
cd /home/j/.openclaw/workspace || exit 0
OUT=$(timeout 120 python3 tools/tasks-audit.py --fix 2>&1)
RC=$?
echo "$(date '+%F %T') $OUT" >> state/work/tasks-audit.log
case "$OUT" in
  *"非法状态"*|*"新增陈旧"*|*"AUDIT_ERROR"*)
    timeout 20 bash tools/notify.sh --alert "🧹 台账保洁：$OUT" >/dev/null 2>&1 ;;
esac

# 2026-11-02 加：评审池守门人（防文档漂移/池冲突/台账违规）
G=$(timeout 60 python3 tools/review-pool-guard.py 2>&1)
GRC=$?
echo "$(date '+%F %T') [pool-guard] $G" >> state/work/tasks-audit.log
if [ "$GRC" -ne 0 ]; then
  timeout 20 bash tools/notify.sh --alert "🛡️ 评审池体检未过：$G" >/dev/null 2>&1
fi
exit 0
