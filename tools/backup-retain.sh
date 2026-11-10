#!/bin/bash
# backup-retain.sh v2 (2026-10-18 主公拍板)
# 新策略：保留集不动；超出保留数的旧档只查【同名+同大小】副本即可移入回收站，7 天后真删
# 保留集由 backup-manifest.py 每日算 SHA256 入台账；不再为待删档逐一算哈希
[ -n "$BASH_VERSION" ] || { echo "需用 bash 运行: bash $0" >&2; exit 1; }
set -u
. /home/j/.openclaw/workspace/tools/nas-config.sh
LOG=/home/j/.openclaw/workspace/state/backup-retain.log
_LK=/home/j/.openclaw/workspace/state/work/backup-retain.lock
mkdir -p "$(dirname "$_LK")"
exec 9>"$_LK"
flock -n 9 || { echo "$(date '+%F %T') SKIP 已有实例在跑" >> "$LOG"; exit 0; }
NOTIFY=/home/j/.openclaw/workspace/tools/notify.sh
RET_ENV=/home/j/.openclaw/workspace/tools/retention.env
[ -f "$RET_ENV" ] && . "$RET_ENV"
KEEP_D=$(printenv KEEP_D 2>/dev/null || echo 2)
KEEP_EH=$(printenv KEEP_EH 2>/dev/null || echo 7)
KEEP_X=$(printenv KEEP_X 2>/dev/null || echo 2)
KEEP_L=$(printenv KEEP_L 2>/dev/null || echo 0)
KEEP_NAS=$(printenv KEEP_NAS 2>/dev/null || echo 7)
WK=$(printenv WEEKLY_KEEP 2>/dev/null || echo 4)
_ck() { case "$2" in ''|*[!0-9]*) echo "WARN $1 非法('$2')，回落 $3" >> "$LOG"; printf %s "$3";; *) if [ "$2" -lt 1 ]; then echo "WARN $1 <1，回落 $3" >> "$LOG"; printf %s "$3"; else printf %s "$2"; fi;; esac; }
KEEP_D=$(_ck KEEP_D "$KEEP_D" 2)
KEEP_EH=$(_ck KEEP_EH "$KEEP_EH" 7)
KEEP_X=$(_ck KEEP_X "$KEEP_X" 2)
KEEP_L=$(_ck KEEP_L "$KEEP_L" 0)
KEEP_NAS=$(_ck KEEP_NAS "$KEEP_NAS" 5)
BAD=0
DRY=$(printenv DRY_RUN 2>/dev/null || echo 0)
FORCE=$(printenv FORCE_OLD 2>/dev/null || echo 0)
echo "=== $(date '+%F %T') 保留策略 v2（保留集校验 / 超期档只查同名同大小 / 回收站 7 天） DRY=$DRY ===" >> "$LOG"

copy_elsewhere() {
  f=$1; shift
  sz=$(stat -c %s "$f" 2>/dev/null)
  for x in "$@"; do
    y="$x/$(basename "$f")"
    [ -f "$y" ] || continue
    [ "$(stat -c %s "$y" 2>/dev/null)" = "$sz" ] && { echo "$x"; return 0; }
  done
  return 1
}

NAS_LIST=$(mktemp 2>/dev/null || echo /tmp/nas-list.$$)
if nas_guard "$NAS_ARCHIVES" 2>/dev/null; then ls -l "$NAS_ARCHIVES"/*.tar.gz 2>/dev/null | awk '{print $5, $9}' > "$NAS_LIST" 2>/dev/null || true; else : > "$NAS_LIST"; fi
nas_has() { [ -s "$NAS_LIST" ] || return 1; awk -v n="$1" -v s="$2" 'index($2,n)>0 && $1==s {f=1} END{exit !f}' "$NAS_LIST"; }

copies_count() {
  _f=$1; shift
  _sz=$(stat -c %s "$_f" 2>/dev/null) || return 1
  _c=0
  for _d in "$@"; do
    _y="$_d/$(basename "$_f")"
    [ -f "$_y" ] && [ "$(stat -c %s "$_y" 2>/dev/null)" = "$_sz" ] && _c=$((_c+1))
  done
  echo "$_c"
}


sample_hash() { # 2026-11-07: 删前留头/尾 1MB 抽样哈希，写 jsonl 便于日后核对是否删错
  _f=$1; _led=/home/j/.openclaw/workspace/state/backup/del-sample-hash.jsonl
  [ -e "$_f" ] || return 0
  _sz=$(stat -c %s "$_f" 2>/dev/null || echo 0)
  _h1=$(head -c 1048576 "$_f" 2>/dev/null | sha256sum | cut -d' ' -f1)
  _h2=$(tail -c 1048576 "$_f" 2>/dev/null | sha256sum | cut -d' ' -f1)
  printf '{"ts":"%s","file":"%s","size":%s,"head_sha256":"%s","tail_sha256":"%s"}
' "$(date -Iseconds)" "$_f" "$_sz" "$_h1" "$_h2" >> "$_led" 2>/dev/null || true
}
del_old() { # 2026-11-06 v2：D 盘为滚动缓存，直删不搬回收站（同盘搬了不省空间）
  _f=$1; _tr=$2; shift 2
  [ -n "$_f" ] && [ -e "$_f" ] || { echo "  ✗ del_old 参数无效" >> "$LOG"; return 1; }
  case "$_f" in
    /mnt/d/openclaw-backups/*)
      _cc=$(copies_count "$_f" "$@" 2>/dev/null || echo 0)
      if [ "${_cc:-0}" -lt 2 ]; then echo "  ⚠️ 保留(D·别处同size副本仅${_cc:-0}份·需>=2): $(basename "$_f")" >> "$LOG"; BAD=$((BAD+1)); return 1; fi
      sample_hash "$_f"
      { head -c 1 "$_f" >/dev/null 2>&1 && rm -f -- "$_f"; } || return 1
      echo "  🗑 直删(D盘滚动缓存): $(basename "$_f")" >> "$LOG" ;;
    *) sample_hash "$_f"
       mv -f -- "$_f" "$_tr/" || return 1
       echo "  🗑 移回收: $(basename "$_f")" >> "$LOG" ;;
  esac
}

prune() {
  dir=$1; keep=$2; tag=$3; shift 3
  [ -d "$dir" ] || return 0
  tr="$dir/_trash/$(date +%Y%m%d-%H%M)"
  [ "$DRY" = "1" ] || mkdir -p "$tr" 2>/dev/null
  n=0; mon=0; seenwk=""
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    n=$((n+1))
    nm=$(basename "$f"); sz=$(stat -c %s "$f" 2>/dev/null)
    if [ "$n" -le "$keep" ]; then echo "  保留($tag): $nm" >> "$LOG"; continue; fi
    dow=$(date -d "${nm:0:10}" +%u 2>/dev/null || echo 0)
    if [ "$dow" = "1" ] && [ "$mon" -lt "${WK:-4}" ]; then
      wk=$(date -d "${nm:0:10}" +%G-%V 2>/dev/null)
      case " $seenwk " in *" $wk "*) : ;; *) seenwk="$seenwk $wk"; mon=$((mon+1)); echo "  保留($tag·周档 $mon/${WK:-4} 第$wk周·官方格式): $nm" >> "$LOG"; echo "$nm" >> /home/j/.openclaw/workspace/state/weekly-keep.txt; continue;; esac
    fi
    mt=$(stat -c %Y "$f" 2>/dev/null || echo 0)
    if [ $(( $(date +%s) - mt )) -lt 86400 ]; then echo "  SKIP 新写入<24h($tag): $nm" >> "$LOG"; continue; fi
    if w=$(copy_elsewhere "$f" "$@"); then
      if [ "$DRY" = "1" ]; then echo "  [演练] 将移回收($tag·同名同大小在 $w): $nm ($sz)" >> "$LOG"
      else del_old "$f" "$tr" "$@" && echo "  ✔ 清理($tag·副本在 $w·$nm·$sz)" >> "$LOG"; fi
    else
      if [ "$FORCE" = "1" ]; then case "$dir" in /mnt/d/*) echo "  ⚠️ 保留($tag·无副本·FORCE 不直删 D): $nm" >> "$LOG"; BAD=$((BAD+1)) ;; *) del_old "$f" "$tr" "$@" && echo "  ⚠ 强制清理($tag·无副本·$nm·$sz)" >> "$LOG" ;; esac
      elif nas_has "$nm" "$sz"; then
        if [ "$DRY" = "1" ]; then echo "  [演练] 移回收($tag·NAS有同size副本): $nm ($sz)" >> "$LOG"
        else del_old "$f" "$tr" "$@" && echo "  ✔ 清理($tag·NAS有同size副本·$nm·$sz)" >> "$LOG"; fi
      else
      echo "  ⚠️ 保留($tag·别处无同名同大小副本): $nm" >> "$LOG"; BAD=$((BAD+1))
      fi
    fi
  done < <(ls -t "$dir"/*.tar.gz 2>/dev/null)
}

purge_trash() {
  # 2026-10-21 加固：同时清目录与平铺 .tar.gz；入回收时间用 .entered-at/ctime（不是 mtime）；
  # 删除前必须确认别处有同名副本；null 分隔防换行文件名；rm -rf -- 防 - 开头
  d=$1; [ -d "$d" ] || return 0
  find "$d" -maxdepth 1 -mindepth 1 \( -type d -o \( -type f -name '*.tar.gz' \) \) -mtime +7 -ctime +7 -print0 2>/dev/null |
  while IFS= read -r -d '' x; do
    t="$x/.entered-at"
    if [ -f "$t" ]; then age=$(( ( $(date +%s) - $(stat -c %Y "$t") ) / 86400 ))
    else age=$(( ( $(date +%s) - $(stat -c %Z "$x") ) / 86400 )); fi
    [ "$age" -ge 7 ] || continue
    b=$(basename "$x"); found=0
    for o in /mnt/d/openclaw-backups /mnt/e/openclaw-backups /mnt/h/openclaw-backups /home/j/Backups; do
      [ "$o" = "$(dirname "$d")" ] && continue
      if [ -e "$o/$b" ] || [ -e "$o/_trash/$b" ]; then found=1; break; fi
    done
    if [ "$found" != "1" ]; then echo "  ⏭ 跳过(别处无同名副本): $x" >> "$LOG"; continue; fi
    if [ "$DRY" = "1" ]; then echo "  [演练] 清回收(${age}天): $x" >> "$LOG"
    else rm -rf -- "$x" && echo "  🧹 清回收(${age}天): $x" >> "$LOG"; fi
  done
}

prune /mnt/d/openclaw-backups "$KEEP_D" "D盘" /mnt/e/openclaw-backups /mnt/h/openclaw-backups
prune /mnt/e/openclaw-backups "$KEEP_EH" "E盘" /mnt/h/openclaw-backups
prune /mnt/h/openclaw-backups "$KEEP_EH" "H盘" /mnt/e/openclaw-backups
prune /mnt/x/openclaw-backups "$KEEP_X" "X盘" /mnt/e/openclaw-backups /mnt/h/openclaw-backups
[ "${KEEP_L:-0}" -gt 0 ] && prune /home/j/Backups "$KEEP_L" "本地" /mnt/e/openclaw-backups /mnt/h/openclaw-backups

. /home/j/.openclaw/workspace/tools/nas-config.sh
NL=/home/j/.openclaw/workspace/state/tmp/nas-archives.txt
if nas_guard "$NAS_ARCHIVES"; then
  ls -1t "$NAS_ARCHIVES"/*.tar.gz 2>/dev/null | grep -E 'openclaw-backup\.tar\.gz$' > "$NL" || true
else
  : > "$NL"; echo "  ⚠️ 新 NAS 未挂载，本轮跳过 NAS 层保留清理" >> "$LOG"
fi
# 2026-11-06 主公令：群晖只预留 1TB，其余全部用于循环备份（按空间滚动，不再按份数）
RESERVE_GB=${RESERVE_NAS_GB:-1024}
NAS_FREE_GB=0; NAS_SUM_GB=0
if nas_guard "$NAS_ARCHIVES" 2>/dev/null; then
  NAS_FREE_GB=$(df -Pk "$NAS_ARCHIVES" 2>/dev/null | awk 'NR==2{print int($4/1024/1024)}')
  NAS_SUM_GB=$(stat -c %s "$NAS_ARCHIVES"/*.tar.gz 2>/dev/null | awk '{s+=$1} END{printf "%d", s/1024/1024/1024}' || echo 0)
  case "$NAS_SUM_GB" in ''|*[!0-9]*) NAS_SUM_GB=0;; esac
fi
case "${NAS_FREE_GB:-}" in ''|*[!0-9]*) NAS_FREE_GB=0;; esac
case "${NAS_SUM_GB:-}" in ''|*[!0-9]*) NAS_SUM_GB=0;; esac
NAS_BUDGET_GB=$(( NAS_FREE_GB + NAS_SUM_GB - RESERVE_GB ))
[ "$NAS_BUDGET_GB" -lt 0 ] && NAS_BUDGET_GB=0
echo "  群晖空间: 可用 ${NAS_FREE_GB}G + 已用归档 ${NAS_SUM_GB}G - 预留 ${RESERVE_GB}G = 归档预算 ${NAS_BUDGET_GB}G" >> "$LOG"
NAS_ACC_GB=0
i=0; monnas=0; seenwkn=""
while IFS= read -r rf; do
  [ -n "$rf" ] || continue
  i=$((i+1))
  SZ_GB=$(stat -c %s "$rf" 2>/dev/null | awk '{printf "%d", $1/1024/1024/1024}')
  if [ "$(( NAS_ACC_GB + SZ_GB ))" -le "$NAS_BUDGET_GB" ]; then
    NAS_ACC_GB=$(( NAS_ACC_GB + SZ_GB ))
    echo "  保留(群晖·滚动 ${NAS_ACC_GB}/${NAS_BUDGET_GB}G): $(basename "$rf")" >> "$LOG"; continue
  fi
  b=$(basename "$rf")
  dwn=$(date -d "${b:0:10}" +%u 2>/dev/null || echo 0)
  if [ "$dwn" = "1" ] && [ "$monnas" -lt "${WK:-4}" ]; then
    wkn=$(date -d "${b:0:10}" +%G-%V 2>/dev/null)
    case " $seenwkn " in *" $wkn "*) : ;; *) seenwkn="$seenwkn $wkn"; monnas=$((monnas+1)); echo "  保留(群晖·周档 $monnas/${WK:-4} 第$wkn周): $b" >> "$LOG"; continue;; esac
  fi
  rsz=$(stat -c%s "$rf" 2>/dev/null | tr -d ' \r')
  ok=""
  for L in /mnt/h/openclaw-backups /mnt/e/openclaw-backups /mnt/d/openclaw-backups; do
    [ -f "$L/$b" ] || continue
    lsz=$(stat -c%s "$L/$b" 2>/dev/null)
    [ "$lsz" = "$rsz" ] && { ok=$L; break; }
  done
  if [ -n "$ok" ]; then
    if [ "$DRY" = "1" ]; then echo "  [演练] 将移回收(群晖·同名同大小在 $ok): $b" >> "$LOG"
    else mkdir -p "$NAS_ARCHIVES/_trash/$(date +%Y%m%d-%H%M)" && mv -f "$rf" "$NAS_ARCHIVES/_trash/$(date +%Y%m%d-%H%M)/" && echo "  🗑 移入回收(群晖·副本在 $ok): $b" >> "$LOG"; fi
  else
    if [ "$FORCE" = "1" ]; then mkdir -p "$NAS_ARCHIVES/_trash/$(date +%Y%m%d-%H%M)" && mv -f "$rf" "$NAS_ARCHIVES/_trash/$(date +%Y%m%d-%H%M)/" && echo "  🗑 强制移回收(群晖·无副本): $b" >> "$LOG"; else
    echo "  ⚠️ 保留(群晖·本地无同名同大小副本): $b" >> "$LOG"; BAD=$((BAD+1))
    fi
  fi
done < "$NL"

purge_trash /mnt/d/openclaw-backups/_trash
purge_trash /mnt/e/openclaw-backups/_trash
purge_trash /mnt/h/openclaw-backups/_trash
if [ "$DRY" != "1" ]; then find "$NAS_ARCHIVES/_trash" -mindepth 1 -maxdepth 1 -type d -mtime +7 -exec rm -rf {} + >/dev/null 2>&1 || true; fi

_BC=/home/j/.openclaw/workspace/state/retain-bad-count
_old=$(cat "$_BC" 2>/dev/null || echo none)
echo "  D盘剩:$(ls /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null|wc -l) E盘剩:$(ls /mnt/e/openclaw-backups/*.tar.gz 2>/dev/null|wc -l) H盘剩:$(ls /mnt/h/openclaw-backups/*.tar.gz 2>/dev/null|wc -l) 保留集上限 D$KEEP_D/E$KEEP_EH/H$KEEP_EH/群晖$KEEP_NAS" >> "$LOG"
if [ "$BAD" -gt 0 ]; then echo "  ⚠️ 本轮 $BAD 份别处无副本/需人工" >> "$LOG"; fi
if [ "$BAD" != "$_old" ]; then
  echo "$BAD" > "$_BC"
  if [ "$BAD" -gt 0 ]; then bash "$NOTIFY" "⚠️备份保留：$BAD 份在别处找不到同名同大小副本，已保留未动（原 $_old）" >/dev/null 2>&1 || true; fi
fi
WKFILE=/home/j/.openclaw/workspace/state/weekly-keep.txt
[ -f "$WKFILE" ] && sort -u -o "$WKFILE" "$WKFILE" 2>/dev/null
tail -n 120 "$LOG" > "$LOG.t" && mv "$LOG.t" "$LOG"
