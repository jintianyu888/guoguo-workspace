#!/bin/bash
# EH 盘体检（只读）v2 · 2026-10-17 主公令：E/H 必须全树比对，不能只看工作区
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/eh-health.log
DET=$W/state/eh-health-detail.log
TS=$(date "+%F %T")
P=""
add(){ P="$P; $1"; }
: > "$DET"

# 逐棵树比对 E 与 H：参数 = 名称 容差 排除项...
check_tree(){
  local name=$1 tol=$2; shift 2
  local args=() e out n
  for e in "$@"; do args+=(--exclude "$e"); done
  if [ ! -d "/mnt/e/$name" ] || [ ! -d "/mnt/h/$name" ]; then
    add "$name 单边缺失"; echo 0; return 0
  fi
  out=$(timeout 1800 rsync -an --delete --info=none --exclude '*.baiduyun.*' "${args[@]}" "/mnt/e/$name/" "/mnt/h/$name/" 2>/dev/null)
  n=$(printf '%s\n' "$out" | grep -c . || true)
  { echo "== $name 差异 $n 项（容差 $tol）"; printf '%s\n' "$out" | head -20; echo; } >> "$DET"
  [ "$n" -gt "$tol" ] && add "$name 不一致 $n 项"
  echo "$n"
}

# 1) 三棵主树
DW=$(check_tree openclaw-workspaces 50 sheet-music/scores cooking/videos script-mystery/media)
DS=$(check_tree openclaw-store 20)
DC=$(check_tree openclaw-cloud-backup 20)

# 2) 归档目录：只比两边都有的日期（保留份数不同属正常，单边日期不算错）
BK=0
for hd in /mnt/h/openclaw-backups/20*/; do
  [ -d "$hd" ] || continue
  d=$(basename "$hd")
  [ -d "/mnt/e/openclaw-backups/$d" ] || continue
  out=$(timeout 600 rsync -an --delete --info=none "/mnt/e/openclaw-backups/$d/" "/mnt/h/openclaw-backups/$d/" 2>/dev/null)
  n=$(printf '%s\n' "$out" | grep -c . || true)
  BK=$((BK+n))
  [ "$n" -gt 0 ] && echo "== backups/$d 差异 $n 项" >> "$DET"
done
[ "$BK" -gt 5 ] && add "归档目录共 $BK 项不一致"

# 3) 快照新鲜度（store 三件套，>36h 报警）
for IT in scores cooking-videos script-mystery-media; do
  LAT=$(ls -1d /mnt/h/openclaw-store/$IT/20*/ 2>/dev/null | sort | tail -1)
  if [ -z "$LAT" ]; then add "$IT 无快照"; continue; fi
  AGE=$(( ( $(date +%s) - $(stat -c %Y "$LAT/.snapshot-done" 2>/dev/null || stat -c %Y "$LAT") ) / 3600 ))
  [ "$AGE" -gt 36 ] && add "$IT 快照 ${AGE}h 未更新"
done

# 4) 抽查哈希（每个外置库首个文件）
for IT in scores cooking-videos script-mystery-media; do
  LAT=$(ls -1d /mnt/h/openclaw-store/$IT/20*/ 2>/dev/null | sort | tail -1)
  [ -n "$LAT" ] || continue
  f=$(find /mnt/e/openclaw-store/$IT -type f ! -path "*/20*" 2>/dev/null | head -1)
  if [ -n "$f" ]; then
    rel=${f#/mnt/e/openclaw-store/$IT/}
    if [ -f "$LAT/$rel" ]; then
      a=$(sha256sum "$f" 2>/dev/null | cut -d" " -f1); b=$(sha256sum "$LAT/$rel" 2>/dev/null | cut -d" " -f1)
      [ "$a" != "$b" ] && add "哈希不符 $(basename "$f" | cut -c1-30)"
    fi
  fi
done

# 5) 磁盘使用率
for M in /mnt/e /mnt/h; do
  U=$(df "$M" | awk 'NR==2{print $5}' | tr -d "%")
  [ -z "$U" ] && U=0
  [ "$U" -ge 92 ] && add "$M 使用率 $U%"
done

if [ -z "$P" ]; then
  echo "$TS OK EH 体检通过 工作区 $DW · store $DS · 云备份 $DC · 归档 $BK" >> "$LOG"
else
  echo "$TS WARN EH 体检异常:$P" >> "$LOG"
  bash "$W/tools/notify.sh" "EH 盘体检异常:$P（明细见 state/eh-health-detail.log）"
fi
exit 0
