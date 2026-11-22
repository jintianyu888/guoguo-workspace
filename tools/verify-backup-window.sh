#!/bin/bash
# verify-backup-window.sh —— 备份窗口健康验收（任务 #1001 的机器判定）
# 验收：①当日备份 tar.gz 恰 1 个 ②当日真实日志里 database is locked 0 条
#       ③schedule-audit 撞窗 0 ④cron 漏跑 ≤3
# 用法：bash tools/verify-backup-window.sh [YYYY-MM-DD]   rc=0 全绿（默认今天）
# 注意：只扫 *.log。曾因全目录 grep 命中了账本里自己写的结论文字，造成假红。
set -u
cd "$(dirname "$0")/.." || exit 2
day=${1:-$(date +%F)}
fail=0

n=$(ls /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | grep -c "$day")
if [ "$n" = 1 ]; then echo "OK   targz[$day]=$n"; else echo "FAIL targz[$day]=$n (期望 1)"; fail=1; fi

lk=$(find state/log state/work -type f -name '*.log' -exec grep -Ih "database is locked" {} + 2>/dev/null | grep -c "$day")
if [ "$lk" = 0 ]; then echo "OK   database_locked[$day]=$lk"; else echo "FAIL database_locked[$day]=$lk"; fail=1; fi

if python3 tools/schedule-audit.py 2>&1 | grep -q "撞窗】0"; then
  echo "OK   schedule_audit_overlap=0"
else
  echo "FAIL schedule_audit_overlap>0"; fail=1
fi

miss=$(python3 tools/cron-miss.py --hours 26 2>/dev/null | sed -n 's/^漏跑 \([0-9][0-9]*\) .*/\1/p')
miss=${miss:-999}
if [ "$miss" -le 3 ]; then echo "OK   cron_miss=$miss (允许 ≤3)"; else echo "FAIL cron_miss=$miss"; fail=1; fi

[ $fail -eq 0 ] && echo "RESULT PASS" || echo "RESULT FAIL"
exit $fail
