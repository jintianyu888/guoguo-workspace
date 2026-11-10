#!/bin/bash
# d-junk-clean.sh v5 —— 只清"我自己产生的垃圾"，范围硬白名单，别的一律不碰
# 白名单（前缀必须匹配，逐条校验）：
#   /mnt/{d,e,h}/openclaw-backups/.openclaw-backup-publish-*   失败发布残留
#   /mnt/{d,e,h}/openclaw-backups/_trash/*                     我们自己的回收站
#   /mnt/{d,e,h}/openclaw-trash/publish-*                      发布残留回收站
#   /mnt/d/openclaw-backups-fast/_trash/*                              实验线回收站
#   ~/archive/jinyu/openclaw-archives/_trash/* 与 ~/archive/jinyu/openclaw-archives/*.part 群晖侧同类垃圾
set -uo pipefail
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/d-junk-clean.log
LED=$WS/state/trash-ledger.log
LOCK=$WS/state/work/d-junk-clean.lock
DRY=${DRY:-1}
NAS=nas
say(){ echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
exec 9>"$LOCK"; flock -n 9 || { echo "已有实例"; exit 0; }
pgrep -f 'openclaw backup|backup-fast|d-cleanup-2026' >/dev/null 2>&1 && { say "备份/清理在跑，跳过"; exit 0; }

# 硬白名单：只有匹配下面模式的路径才允许动，其它一律拒绝（含用户目录、金鱼/备份、网盘等）
in_scope(){
  local p="$1"
  case "$p" in
    /mnt/d/openclaw-backups/_trash/*|/mnt/e/openclaw-backups/_trash/*|/mnt/h/openclaw-backups/_trash/*) return 0;;
    /mnt/d/openclaw-trash/*|/mnt/e/openclaw-trash/*|/mnt/h/openclaw-trash/*) return 0;;
    /mnt/d/openclaw-backups-fast/_trash/*) return 0;;
    /home/j/.openclaw-trash/*) return 0;;
    /home/j/backup-stage/.openclaw-backup-publish-*) return 0;;
    /mnt/*/openclaw-backups/.openclaw-backup-publish-*) return 0;;
    /var/services/homes/guoguonas/archive/jinyu/openclaw-archives/_trash/*) return 0;;
    /var/services/homes/guoguonas/archive/jinyu/openclaw-archives/*.part) return 0;;
  esac
  return 1
}

n=0; freed=0; SKIPPED=0
stamp(){ local d="$1"; [ -f "$d/.entered-at" ] || date +%s > "$d/.entered-at" 2>/dev/null || true; }

# ---- 1) 失败发布残留（>6h）→ 同盘回收站（mv，秒级）----
for disk in /mnt/d /mnt/e /mnt/h; do
  src="$disk/openclaw-backups"; tr="$disk/openclaw-trash"
  [ -d "$src" ] || continue
  while IFS= read -r d; do
    [ -d "$d" ] || continue
    in_scope "$d" || { say "不在白名单，跳过 $d"; continue; }
    sz=$(du -sb "$d" 2>/dev/null | awk '{print $1}'); sz=${sz:-0}
    say "publish 残留 $(basename "$d") $sz 字节"
    if [ "$DRY" = "0" ]; then
      mkdir -p "$tr"; b=$(basename "$d")
      if mv -- "$d" "$tr/publish-$b"; then echo "$(date '+%F %T') move $d $sz" >> "$LED"; n=$((n+1)); freed=$((freed+sz)); fi
    fi
  done < <(find "$src" -maxdepth 1 -type d -name '.openclaw-backup-publish-*' -mmin +360 2>/dev/null)
done

# ---- 2) 我们自己的回收站：进站戳满 7 天才删 ----
for root in /mnt/d/openclaw-backups/_trash /mnt/e/openclaw-backups/_trash /mnt/h/openclaw-backups/_trash /mnt/d/openclaw-trash /mnt/e/openclaw-trash /mnt/h/openclaw-trash /mnt/d/openclaw-backups-fast/_trash /home/j/.openclaw-trash; do
  [ -d "$root" ] || continue
  while IFS= read -r e; do
    [ -d "$e" ] || continue
    in_scope "$e" || { say "不在白名单，跳过 $e"; continue; }
    stamp "$e"
    if ! ts=$(cat "$e/.entered-at" 2>/dev/null); then say "读戳失败，跳过 $e"; SKIPPED=$((SKIPPED+1)); continue; fi
    case "$ts" in ''|*[!0-9]*) say "戳内容异常($ts)，跳过 $e"; SKIPPED=$((SKIPPED+1)); continue;; esac
    NOW=$(date +%s)
    if [ "$ts" -gt "$NOW" ] || [ "$ts" -lt $((NOW-630720000)) ]; then say "戳越界($ts)，跳过 $e"; SKIPPED=$((SKIPPED+1)); continue; fi
    age_d=$(( ( NOW - ts ) / 86400 ))
    [ "$age_d" -ge 7 ] || continue
    sz=$(du -sb "$e" 2>/dev/null | awk '{print $1}'); sz=${sz:-0}
    say "回收站到期 $e $sz 字节"
    if [ "$DRY" = "0" ]; then rm -rf -- "$e" && { echo "$(date '+%F %T') purge $e $sz" >> "$LED"; n=$((n+1)); freed=$((freed+sz)); }; fi
  done < <(find "$root" -mindepth 1 -maxdepth 1 -type d 2>/dev/null)
done

# ---- 3) 半截 .part（>24h）----
for root in /mnt/d/openclaw-backups /mnt/e/openclaw-backups /mnt/h/openclaw-backups /mnt/d/openclaw-backups-fast; do
  [ -d "$root" ] || continue
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    in_scope "$f" || continue
    sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
    say "半截 .part $f $sz 字节"
    if [ "$DRY" = "0" ]; then rm -f -- "$f" && { echo "$(date '+%F %T') part $f $sz" >> "$LED"; n=$((n+1)); freed=$((freed+sz)); }; fi
  done < <(find "$root" -maxdepth 2 -name "*.part" -mmin +1440 -type f 2>/dev/null)
done

# ---- 4) 群晖侧同类垃圾：只碰 openclaw-archives 下的 _trash 与 .part ----
if timeout 20 ssh -o BatchMode=yes -o ConnectTimeout=8 "$NAS" true 2>/dev/null; then
  REMOTE='A="$HOME/archive/jinyu/openclaw-archives"; [ -d "$A" ] || exit 0
    for d in "$A/_trash"/*; do [ -d "$d" ] || continue
      if [ ! -f "$d/.entered-at" ]; then date +%s > "$d/.entered-at" 2>/dev/null || continue; fi
      ts=$(cat "$d/.entered-at" 2>/dev/null) || continue
      case "$ts" in ''|*[!0-9]*) continue;; esac
      [ "$ts" -le "$(date +%s)" ] || continue
      [ $(( ($(date +%s) - ts) / 86400 )) -ge 7 ] && echo "$d"; done
    find "$A" -maxdepth 1 -name "*.part" -mmin +1440 -type f -print 2>/dev/null'
  mapfile -t list < <(timeout 90 ssh -o BatchMode=yes "$NAS" "$REMOTE" 2>/dev/null)
  for p in "${list[@]:-}"; do
    [ -n "$p" ] || continue
    case "$p" in /var/services/homes/guoguonas/archive/jinyu/openclaw-archives/*) ;; *) say "NAS 越界，拒绝 $p"; continue;; esac
    say "NAS 垃圾 $p"
    if [ "$DRY" = "0" ]; then timeout 600 ssh -o BatchMode=yes "$NAS" "rm -rf -- '$p'" 2>/dev/null && { echo "$(date '+%F %T') nas $p" >> "$LED"; n=$((n+1)); }; fi
  done
else say "群晖不可达，跳过"; fi

say "完成：处理 $n 项，释放约 $((freed/1024/1024/1024))G（DRY=$DRY）"
if [ "$DRY" = "0" ] && { [ "$n" -gt 0 ] || [ "$SKIPPED" -gt 0 ]; }; then bash "$WS/tools/notify.sh" "定期清理：$n 项，释放约 $((freed/1024/1024/1024))G；因戳异常跳过 $SKIPPED 项" >/dev/null 2>&1 || true; fi
exit 0
