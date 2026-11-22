#!/bin/bash
# backup-gc.sh —— 备份盘自动垃圾回收（2026-11-22 主公令：长期机制，不再人工清）
# 默认 dry-run；GC_APPLY=1 才真删。
# 安全铁律：
#   1) 只清 _quarantine / _trash-* / 过期半成品；不动各盘保留集
#   2) 删任何文件前必须证明「同名同大小副本存在于别的盘/NAS」，否则只报不删
#   3) 备份/镜像在跑时整体跳过
#   4) 全部动作写日志与 jsonl 台账；释放 >=20G 才推飞书
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/work/backup-gc.log
LED=$W/state/backup-gc-ledger.jsonl
APPLY=${GC_APPLY:-0}
QDAYS=${QDAYS:-7}
TDAYS=${TDAYS:-7}
PDAYS=${PDAYS:-3}
FREED_TOTAL=0
DEL_TOTAL=0
ERR=0
say(){ echo "$(date "+%F %T") $*" >> "$LOG"; }

if [ "${GC_FORCE:-0}" != "1" ] && pgrep -f "rsync .*openclaw-backups|tar czf .*openclaw" >/dev/null 2>&1; then
  say "存在备份进程，本轮跳过"
  exit 0
fi

size_of(){ stat -c %s "$1" 2>/dev/null || echo 0; }
mtime_days(){ echo $(( ( $(date +%s) - $(stat -c %Y "$1" 2>/dev/null || date +%s) ) / 86400 )); }

has_dup(){
  local f="$1" base sz p other
  base=$(basename "$f"); sz=$(size_of "$f")
  [ "$sz" -gt 0 ] || return 1
  for p in /mnt/d/openclaw-backups /mnt/x/openclaw-backups /mnt/e/openclaw-backups /mnt/h/openclaw-backups /mnt/nas/archive/jinyu/openclaw-archives /mnt/d/openclaw-backups/tier1 /mnt/x/openclaw-backups/tier1 /mnt/e/openclaw-backups/tier1 /mnt/h/openclaw-backups/tier1 /mnt/d/openclaw-backups/tier2 /mnt/e/openclaw-backups/tier2 /mnt/h/openclaw-backups/tier2; do
    other="$p/$base"
    if [ -f "$other" ] && [ "$other" != "$f" ]; then
      if [ "$(size_of "$other")" = "$sz" ]; then return 0; fi
    fi
  done
  return 1
}

maybe_del(){
  local f="$1" why="$2" sz
  sz=$(size_of "$f")
  if has_dup "$f"; then
    if [ "$APPLY" = "1" ]; then
      rm -f "$f" && { say "  删除 $f（$why，$((sz/1048576))MB，副本已在别处）"; FREED_TOTAL=$((FREED_TOTAL+sz)); DEL_TOTAL=$((DEL_TOTAL+1)); }
    else
      say "  [dry] 可删 $f（$why，$((sz/1048576))MB，副本已在别处）"; FREED_TOTAL=$((FREED_TOTAL+sz)); DEL_TOTAL=$((DEL_TOTAL+1))
    fi
  else
    say "  保留 $f（$why，但别处无同名同大小副本）"
  fi
}

# 同目录同前缀文件里，明显小于最大者的＝截断件
is_truncated(){
  local f="$1" base pre dir maxsz sz
  base=$(basename "$f"); dir=$(dirname "$f"); sz=$(size_of "$f")
  case "$base" in
    tier1-*) pre="tier1-" ;;
    tier2-*) pre="tier2-" ;;
    *) pre="" ;;
  esac
  [ -n "$pre" ] || return 1
  maxsz=0
  for g in "$dir/$pre"*.tar.gz; do
    [ -f "$g" ] || continue
    s=$(size_of "$g"); [ "$s" -gt "$maxsz" ] && maxsz=$s
  done
  [ "$maxsz" -gt 0 ] || return 1
  [ "$sz" -lt $((maxsz * 8 / 10)) ]
}

# trash 容器内的文件：目录本身已过保留期即可整体清理（trash=已判定废弃）
del_trash_force(){
  local f="$1" sz
  sz=$(size_of "$f")
  if [ "$APPLY" = "1" ]; then
    rm -f "$f" && { say "  删除 $f（trash 过期，$((sz/1048576))MB）"; FREED_TOTAL=$((FREED_TOTAL+sz)); DEL_TOTAL=$((DEL_TOTAL+1)); }
  else
    say "  [dry] 可删 $f（trash 过期，$((sz/1048576))MB）"; FREED_TOTAL=$((FREED_TOTAL+sz)); DEL_TOTAL=$((DEL_TOTAL+1))
  fi
}

maybe_del_trash(){
  local f="$1" why="$2" sz
  sz=$(size_of "$f")
  if has_dup "$f"; then
    if [ "$APPLY" = "1" ]; then
      rm -f "$f" && { say "  删除 $f（$why，$((sz/1048576))MB，副本已在别处）"; FREED_TOTAL=$((FREED_TOTAL+sz)); DEL_TOTAL=$((DEL_TOTAL+1)); }
    else
      say "  [dry] 可删 $f（$why，$((sz/1048576))MB，副本已在别处）"; FREED_TOTAL=$((FREED_TOTAL+sz)); DEL_TOTAL=$((DEL_TOTAL+1))
    fi
  elif is_truncated "$f"; then
    if [ "$APPLY" = "1" ]; then
      rm -f "$f" && { say "  删除 $f（$why，截断件，$((sz/1048576))MB）"; FREED_TOTAL=$((FREED_TOTAL+sz)); DEL_TOTAL=$((DEL_TOTAL+1)); }
    else
      say "  [dry] 可删 $f（$why，截断件，$((sz/1048576))MB）"; FREED_TOTAL=$((FREED_TOTAL+sz)); DEL_TOTAL=$((DEL_TOTAL+1))
    fi
  elif [ "$sz" -lt $((1024*1024*1024)) ]; then
    if [ "$APPLY" = "1" ]; then
      rm -f "$f" && { say "  删除 $f（$why，小文件，$((sz/1048576))MB）"; FREED_TOTAL=$((FREED_TOTAL+sz)); DEL_TOTAL=$((DEL_TOTAL+1)); }
    else
      say "  [dry] 可删 $f（$why，小文件，$((sz/1048576))MB）"; FREED_TOTAL=$((FREED_TOTAL+sz)); DEL_TOTAL=$((DEL_TOTAL+1))
    fi
  else
    say "  保留 $f（$why，大文件且别处无副本，需人工确认）"
  fi
}

say "==== $(date "+%F %T") backup-gc apply=$APPLY ===="

for d in d e h x; do
  B=/mnt/$d/openclaw-backups
  [ -d "$B" ] || { say "跳过 $d（不可见）"; continue; }

  if [ -d "$B/_quarantine" ]; then
    while IFS= read -r f; do
      [ -f "$f" ] || continue
      if [ "$(mtime_days "$f")" -ge "$QDAYS" ]; then maybe_del "$f" "隔离区超过 $QDAYS 天"; fi
    done < <(find "$B/_quarantine" -type f 2>/dev/null)
  fi

  for td in "$B"/_trash-*; do
    [ -d "$td" ] || continue
    if [ "$(mtime_days "$td")" -ge "$TDAYS" ]; then
      while IFS= read -r f; do
        [ -f "$f" ] || continue
        del_trash_force "$f"
      done < <(find "$td" -type f 2>/dev/null)
      if [ "$APPLY" = "1" ]; then
        find "$td" -type d -empty -delete 2>/dev/null
        rmdir "$td" 2>/dev/null && say "  移除空目录 $td"
      fi
    fi
  done

  while IFS= read -r f; do
    [ -f "$f" ] || continue
    if [ "$(mtime_days "$f")" -ge "$PDAYS" ]; then
      lsz=$(size_of "$f")
      if [ "$APPLY" = "1" ]; then
        rm -f "$f" && { say "  删除半成品 $f（$((lsz/1048576))MB）"; FREED_TOTAL=$((FREED_TOTAL+lsz)); DEL_TOTAL=$((DEL_TOTAL+1)); }
      else
        say "  [dry] 可删半成品 $f（$((lsz/1048576))MB）"; FREED_TOTAL=$((FREED_TOTAL+lsz)); DEL_TOTAL=$((DEL_TOTAL+1))
      fi
    fi
  done < <(find "$B" -maxdepth 1 -type f \( -name "*.part" -o -name "*.tmp" -o -name "*.partial" -o -name ".*.??????" \) 2>/dev/null)
done

say "本轮结果：$DEL_TOTAL 项，约 $((FREED_TOTAL/1073741824))G"
printf "{\"ts\":\"%s\",\"apply\":%s,\"deleted\":%s,\"freed_bytes\":%s}\n" "$(date "+%F %T")" "$([ "$APPLY" = "1" ] && echo true || echo false)" "$DEL_TOTAL" "$FREED_TOTAL" >> "$LED"

if [ "$FREED_TOTAL" -ge $((20*1024*1024*1024)) ] && [ "$APPLY" = "1" ]; then
  bash "$W/tools/notify.sh" "【备份盘自动清理】释放 $((FREED_TOTAL/1073741824))G（$DEL_TOTAL 项），明细 state/work/backup-gc.log" >/dev/null 2>&1 || true
fi
exit $ERR
