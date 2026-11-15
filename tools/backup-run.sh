#!/bin/bash
# backup-run.sh v1.0 —— 备份唯一入口（记账 + 跑原链路 + 记录结果）
set -u
export PATH=/home/j/.npm-global/bin:/usr/bin:/bin
W=/home/j/.openclaw/workspace
LED="python3 $W/tools/backup-ledger.py"
before=$($LED count 2>/dev/null || echo 0)
$LED scan >/dev/null 2>&1 || true
RID=$($LED run-start nightly 2>/dev/null || echo "")
echo "=== $(date "+%F %T") backup-run 开始 run=${RID:-none}" >> "$W/state/work/bk-run.log"
bash "$W/tools/backup-with-quiet.sh" bash "$W/tools/nas-push-archive.sh" create
rc=$?
$LED scan >/dev/null 2>&1 || true
after=$($LED count 2>/dev/null || echo 0)
produced=$(( after - before ))
res=ok; [ "$rc" -eq 0 ] || res=fail
[ -n "$RID" ] && $LED run-end "$RID" "$res" "$produced" --note "rc=$rc" >/dev/null 2>&1 || true
echo "=== $(date "+%F %T") backup-run 结束 rc=$rc 新增归档=$produced" >> "$W/state/work/bk-run.log"
exit $rc