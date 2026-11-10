#!/bin/bash
# manifest-nightly.sh —— 每日增量生成备份清单（名+大小+SHA256），只补缺失/变更，不动文件
set -u
# 2026-11-02：bash 是“边执行边按字节偏移读脚本文件”，运行中改写脚本会让它读到
# 半截新行（08:06 起跑、08:51 被改写 → 实测 "MIN:-60}" unbound variable）。
# 启动即把自身快照到 /tmp 再 exec，之后的任何编辑都影响不到本次运行。
if [ "${MANIFEST_NIGHTLY_SNAPSHOT:-0}" != "1" ]; then
  SELF="$(readlink -f "$0" 2>/dev/null || echo "$0")"
  umask 077
  SNAP="$(mktemp /tmp/manifest-nightly.XXXXXX.sh 2>/dev/null)" || { echo "[$(date "+%F %T")] 快照失败，拒绝运行" >> /home/j/.openclaw/workspace/state/work/manifest-nightly.log; exit 1; }
  if ! cp -f "$SELF" "$SNAP" 2>/dev/null; then
    rm -f "$SNAP"; echo "[$(date "+%F %T")] 快照复制失败，拒绝运行" >> /home/j/.openclaw/workspace/state/work/manifest-nightly.log; exit 1
  fi
  chmod 700 "$SNAP"
  export MANIFEST_NIGHTLY_SNAPSHOT=1 MANIFEST_NIGHTLY_SNAP="$SNAP"
  exec bash "$SNAP" "$@"
fi
# 快照副本退出时自清，避免 /tmp 堆积
[ -n "${MANIFEST_NIGHTLY_SNAP:-}" ] && trap 'rm -f "$MANIFEST_NIGHTLY_SNAP"' EXIT
W=/home/j/.openclaw/workspace
LOG=$W/state/work/manifest-nightly.log
PY=$W/tools/backup-manifest.py
LOCK=$W/state/work/manifest.lock
# CAP：单盘上限（分钟）。2026-11-02 实测：D 盘增量 16 分钟、E 盘 50 分钟；
# 按机械盘顺序读 ~120MB/s、日增 ~70G 估，增量稳态约 10-12 分钟，取 20 分钟留余量。
CAP=${CAP_MINUTES:-30}
# 全局预算：三盘总时长硬上限。2026-11-02 双审（MiniMax-M3 + qwen3.8-max）要求
# 「不靠外层超时切尾巴，脚本自己管全局预算，没算完明天增量继续」。
TOTAL_BUDGET=${TOTAL_BUDGET_MIN:-60}
START_TS=$(date +%s)
mkdir -p "$W/state/work"
exec 9>"$LOCK"
flock -n 9 || { echo "[$(date "+%F %T")] 已有实例在跑，跳过" >> "$LOG"; exit 0; }
log() { echo "[$(date "+%F %T")] $*" >> "$LOG"; }
log "开始（每盘上限 ${CAP} 分钟，全局预算 ${TOTAL_BUDGET} 分钟）"
fail=0
for d in /mnt/d/openclaw-backups /mnt/e/openclaw-backups /mnt/h/openclaw-backups; do
  [ -d "$d" ] || continue
  used=$(( ($(date +%s) - START_TS) / 60 ))
  left=$(( TOTAL_BUDGET - used ))
  if [ "$left" -le 0 ]; then
    log "[预算用尽 ${used}/${TOTAL_BUDGET} 分] 跳过 $d，明天增量继续"
    continue
  fi
  cap=$CAP; [ "$cap" -gt "$left" ] && cap=$left
  out=$(python3 "$PY" --root "$d" --max-minutes "$cap" 2>&1) || fail=1
  log "[本盘限 ${cap} 分｜总用 ${used} 分] $out"
done
if [ "$fail" = "1" ]; then log "❌ 有盘生成失败"; bash "$W/tools/notify.sh" "⚠️ 备份清单生成失败" "见 state/work/manifest-nightly.log"; exit 2; fi
log "完成"