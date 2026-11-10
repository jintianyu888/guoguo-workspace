#!/bin/bash
# backup-drill-nightly.sh —— 恢复演练（独立任务，方案A 拆分）
# 2026-10-21 创建：避免与快速审查挤在同一 7 分钟内被宿主 SIGTERM 掐断
set -u -o pipefail
W=/home/j/.openclaw/workspace
OUT=$W/state/backup-drill; mkdir -p "$OUT" "$W/state/work"
R=$OUT/$(date +%Y%m%d).md
exec 210>"$W/state/work/backup-drill.lock"
flock -n 210 || { echo "已有实例在跑，退出"; exit 0; }
echo "# 恢复演练 $(date '+%F %T')" > "$R"
echo "启动 PID=$$" >> "$R"
start=$(date +%s)
timeout 1800 bash "$W/tools/backup-drill.sh" >> "$R" 2>&1
rc=$?
dur=$(( $(date +%s) - start ))
echo >> "$R"
echo "结果: rc=$rc 耗时=${dur}s" >> "$R"
if [ "$rc" -eq 124 ]; then echo "⚠️ drill 超时 1800s 被终止（非完整结论）" >> "$R"; fi
echo "报告: $R"
if [ "$rc" -ne 0 ]; then
  bash "$W/tools/notify.sh" "🔴 恢复演练失败 rc=$rc 耗时=${dur}s 详见 $R" >/dev/null 2>&1 || true
fi
exit "$rc"
