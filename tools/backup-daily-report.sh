#!/bin/bash
# backup-daily-report.sh v1.0 —— 每日备份台账渲染
set -u
export PATH=/home/j/.npm-global/bin:/usr/bin:/bin
W=/home/j/.openclaw/workspace
LED="python3 $W/tools/backup-ledger.py"
OUT=$W/docs/备份台账-$(date +%Y-%m).md
TMP=/tmp/bk-ledger.$$
$LED scan >/dev/null 2>&1
{
echo "# 备份台账 $(date '+%F %H:%M')"
echo
echo '> 唯一真源：state/ledger/backups.db（tools/backup-ledger.py 维护，禁止手改）'
echo
echo '## 每日归档（近 30 天）'
echo
echo '    '
$LED report --days 30
echo
echo '## 最近运行记录'
echo
$LED runs -n 15
} > "$TMP"
mkdir -p "$W/state/backup"
mv -f "$TMP" "$OUT"
cp -f "$OUT" "$W/state/backup/ledger-latest.md"
echo "台账已更新: $OUT"