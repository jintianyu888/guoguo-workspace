#!/bin/bash
# backup-butler-check.sh v1.0 — 备份管家账本核对（只读，2026-11-15 主公令第1条）
set -u
export PATH=/usr/bin:/bin
W=/home/j/.openclaw/workspace
LED="python3 $W/tools/backup-ledger.py"
ok=1
echo "== 备份账本核对 $(date '+%F %T')"
$LED scan >/dev/null 2>&1
echo
echo "[1] 近 7 天归档分布"
$LED report --days 7 | head -14
echo
echo "[2] 今日份数"
T=$(date +%F); N=$($LED count --day "$T" 2>/dev/null || echo 0)
echo "今日 $T 归档份数：$N（应为 1）"
[ "$N" -eq 1 ] || { echo "⚠️ 今日份数异常（$N）"; ok=0; }
echo
echo "[3] 单盘位风险"
singles=$($LED report --days 7 | grep -c '仅1份' || true)
echo "近 7 天只有 1 个盘位的归档：$singles 份"
[ "$singles" -eq 0 ] || { echo "⚠️ 存在单盘位归档，建议补副本"; ok=0; }
echo
echo "[4] 残片"
$LED report --days 1 | sed -n '/残片/,$p' | head -6
echo
echo "[5] 最近运行"
$LED runs -n 5 2>/dev/null | head -8
echo
echo "[6] 看门狗"
bash $W/tools/backup-watchdog.sh 2>&1 | tail -4
echo
[ $ok -eq 1 ] && echo "结论：账本正常" || echo "结论：发现异常，见上"
exit $((1-ok))