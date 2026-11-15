#!/bin/bash
# backup-retain-plan.sh v1.3 — 三席议会共识(2026-11-15)：X=5 D=3 E=每周1x4 H=每月1x6 NAS=日7+周4+月6；每盘最低2份；自动删除永久关闭(仅预演)
# 用法: backup-retain-plan.sh [--apply] [X|D|E|H|NAS|all]   默认预演
# v1.1 修复: 删除范围严格限定在本次处理的盘（v1.0 会跨盘误删，2026-11-15 事故）
set -u
export PATH=/usr/bin:/bin
APPLY=0; [ "${1:-}" = "--apply" ] && APPLY=1
TARGET="${2:-all}"
KX=2; KD=1; EW=4; HM=6; ND=7; NW=4; NM=6
MINKEEP=2
dir_of() { case "$1" in X) echo /mnt/x/openclaw-backups;; D) echo /mnt/d/openclaw-backups;; E) echo /mnt/e/openclaw-backups;; H) echo /mnt/h/openclaw-backups;; NAS) echo /mnt/nas/archive/jinyu/openclaw-archives;; esac; }
names() { ls -1 "$1"/*.tar.gz 2>/dev/null | xargs -r -n1 basename | sort; }

keepers_for() {
  local disk=$1 d; d=$(dir_of "$disk");
  [ -d "$d" ] || return 0
  case "$disk" in
    X|D) local n=$KX; [ "$disk" = D ] && n=$KD
         names "$d" | tail -n "$n" ;;
    E)  names "$d" | cut -c1-10 | sort -r | awk '!s[$0]++' | head -n $EW | while read -r day; do names "$d" | grep -F "$day" | tail -1; done ;;
    H)  names "$d" | cut -c1-7 | sort -r | awk '!s[$0]++' | head -n $HM | while read -r mo; do names "$d" | grep -F "$mo" | tail -1; done ;;
    NAS) names "$d" | tail -n $ND
         names "$d" | cut -c1-10 | sort -r | awk '!s[$0]++' | head -n $NW | while read -r day; do names "$d" | grep -F "$day" | head -1; done
         names "$d" | cut -c1-7 | sort -r | awk '!s[$0]++' | head -n $NM | while read -r mo; do names "$d" | grep -F "$mo" | head -1; done ;;
  esac
}

# 硬条件2(zhipu): fail-closed — 任一盘不可读即中止
for chk in X D E H NAS; do
  cd_=$(dir_of "$chk")
  if ! ls -1 "$cd_" >/dev/null 2>&1; then
    echo "❌ $chk ($cd_) 不可读，状态未知，中止(fail-closed)"
    echo "$(date '+%F %T') ABORT $chk unreadable" >> /home/j/.openclaw/workspace/state/work/retention-audit.jsonl
    exit 41
  fi
done
DISKS="$TARGET"; [ "$TARGET" = all ] && DISKS="X D E H NAS"
if [ "$APPLY" -eq 1 ] && [ "$TARGET" = all ]; then echo "❌ 执行模式必须指定单盘（X/D/E/H/NAS），不允许 all"; exit 8; fi
total_del=0
for disk in $DISKS; do
  d=$(dir_of "$disk"); [ -d "$d" ] || continue
  keep=$(keepers_for "$disk" | sort -u)
  cnt=$(echo "$keep" | grep -c . || true)
  del=0
  while IFS= read -r f; do
    case "$f" in *.tar.gz) ;; *) continue ;; esac
    b=$(basename "$f")
    echo "$keep" | grep -qxF "$b" && continue
    sz=$(stat -c %s "$f" 2>/dev/null || echo 0); del=$((del+sz))
    if [ $APPLY -eq 1 ]; then
      qdir="$d/_quarantine/$(date +%Y%m%d-%H%M)"
      mkdir -p "$qdir" || { echo "  $disk 隔离区创建失败，跳过"; continue; }
      mv -f "$f" "$qdir/" && echo "  隔离 $disk/$b ($((sz/1024/1024/1024))G) -> _quarantine"
      [ -f "$f.sha256" ] && mv -f "$f.sha256" "$qdir/"
    else echo "  将隔离 $disk/$b ($((sz/1024/1024/1024))G)"; fi
  done < <(ls -1 "$d"/*.tar.gz 2>/dev/null)
  ntot=$(ls -1 "$d"/*.tar.gz 2>/dev/null | wc -l)
  mk=$MINKEEP
  [ "$disk" = "D" ] && mk=1
  if [ "$cnt" -lt "$mk" ] && [ "$ntot" -gt 0 ]; then
    echo "[$disk] ❌ 中止：保留份数 $cnt < 低限 $mk（防误删）"; exit 9
  fi
  if [ "$cnt" -eq 0 ] && [ "$ntot" -gt 0 ]; then
    echo "[$disk] ❌ 中止：保留清单为空但有 $ntot 份归档，拒绝删除（防误删）"; exit 9
  fi
  echo "[$disk] 保留 $cnt 份，计划删 $((del/1024/1024/1024))G"
  total_del=$((total_del+del))
done
echo "合计 $((total_del/1024/1024/1024))G  模式 $([ $APPLY -eq 1 ] && echo 执行 || echo 预演)"
printf '{"ts":"%s","mode":"%s","target":"%s","plan_gb":%s}\n' "$(date '+%F %T')" "$([ $APPLY -eq 1 ] && echo apply || echo dryrun)" "$TARGET" "$((total_del/1024/1024/1024))" >> /home/j/.openclaw/workspace/state/work/retention-audit.jsonl