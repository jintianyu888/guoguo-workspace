#!/bin/bash
# oc-cache-janitor.sh v3（2026-11-10 18:25）
# 背景：OpenClaw 每次只读开状态库（几乎每次工具调用都会经 spawn-broker 起一个只读 worker）
#       都会把 ~145MB 的 session 库整份复制成 openclaw-sqlite-readonly-v2-* 目录，且不自动删。
#       v1 放 ~/.cache 里 → 持续写盘 → WSL vhdx 只增不减。
# v2 只清 /dev/shm/oc-cache。
# v3 更正（实测）：软链 ~/.cache/openclaw -> tmpfs 并不能让快照落内存 ——
#   快照实际建在「临时目录」~/.cache/openclaw-1000 下（fs-safe 的 fallback 临时目录），
#   而该目录绝不能是软链（会令整个 CLI 报 Unsafe fallback 全挂）。
#   故 v3 同时清内存盘与实体临时目录，双保险；根治靠 #970（TMPDIR 指向 /dev/shm 实体目录，重启窗口生效）。
set -u
DIRS=${OC_SNAP_DIRS:-"/dev/shm/oc-cache /home/j/.cache/openclaw-1000"}
LOG=/home/j/.openclaw/workspace/state/work/cache-janitor.log
MIN_AGE=${OC_SNAP_MIN_AGE:-5}      # 分钟
MAX_KEEP_GB=${OC_SNAP_MAX_GB:-2}   # 每个目录上限（GB）
mkdir -p "$(dirname "$LOG")"

for D in $DIRS; do
  [ -d "$D" ] || continue
  total_kb=$(du -sk "$D" 2>/dev/null | awk '{print $1}')
  total_gb=$(( ${total_kb:-0} / 1024 / 1024 ))
  echo "[$(date '+%F %T')] $D 起始 ${total_gb}G (上限 ${MAX_KEEP_GB}G)" >>"$LOG"
  [ "$total_gb" -le "$MAX_KEEP_GB" ] && continue

  BUSY=$(lsof -w -n 2>/dev/null | awk -v d="$D" 'index($NF,d){print $NF}' | xargs -r -n1 dirname 2>/dev/null | sort -u | tr '\n' '|')

  freed=0; del=0
  for dir in "$D"/openclaw-sqlite-readonly-v2-*; do
    [ -e "$dir" ] || continue
    age_min=$(( ( $(date +%s) - $(stat -c %Y "$dir") ) / 60 ))
    [ "$age_min" -lt "$MIN_AGE" ] && continue
    case "$BUSY" in *"$dir"*) continue ;; esac
    sz=$(du -sk "$dir" 2>/dev/null | awk '{print $1}')
    rm -rf -- "$dir" && { freed=$((freed + ${sz:-0})); del=$((del+1)); }
  done

  after_kb=$(du -sk "$D" 2>/dev/null | awk '{print $1}')
  echo "[$(date '+%F %T')] $D 删除 $del 个，释放 $((freed/1024))MB，现存 $(( ${after_kb:-0} / 1024 ))MB" >>"$LOG"
done
