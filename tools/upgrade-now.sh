#!/usr/bin/env bash
# upgrade-now.sh —— 「备份完成后自动升级」一次性执行体（2026-11-21 主公令）
# 顺序：等备份锁释放 → 快照/安装/重启/验证/失败自动回滚（全在 upgrade-openclaw.sh 内）
# 用法：bash tools/upgrade-now.sh <目标版本> [--force]
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/work/upgrade-now.log
TGT="${1:?用法: upgrade-now.sh <版本> [--force]}"
FORCE="${2:-}"
exec >>"$LOG" 2>&1
echo "=== $(date "+%F %T") upgrade-now 启动 目标=$TGT 参数=$FORCE"

# 1) 等备份跑完（最多等 4 小时；期间不抢锁，只观察）
i=0
while fuser "$W/state/work/.backup.lock" >/dev/null 2>&1 || pgrep -f "nas-push-archive.sh create" >/dev/null 2>&1; do
  i=$((i+1))
  [ $i -gt 480 ] && { echo "$(date "+%F %T") 等备份超时(4h)，放弃升级"; exit 3; }
  [ $((i % 12)) -eq 0 ] && echo "$(date "+%F %T") 备份仍在跑，继续等（已等 $((i/12)) 分钟）"
  sleep 30
done
echo "$(date "+%F %T") 备份已结束，开始升级"

# 2) 升级（含四库快照、安装、重启、硬验证、13 项自检、失败自动回滚）
bash "$W/tools/upgrade-openclaw.sh" --version="$TGT" $FORCE
rc=$?
echo "$(date "+%F %T") upgrade-now 结束 rc=$rc"
exit $rc