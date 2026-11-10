#!/bin/bash
# nas-hash-verify.sh (2026-10-18 主公选 A) —— 两端各自本机算 SHA-256，一致才删群晖旧份
# 远端(群晖)本机算，不通过 9p 网络读；本地 H 盘本机算。零 token。
set -u
W=/home/j/.openclaw/workspace
NAS=nas
RD=/var/services/homes/guoguonas/archive/jinyu/openclaw-archives
LD=/mnt/h/openclaw-backups
LOG=$W/state/work/hash-verify.log
LED=$W/state/backup-hash-ledger.jsonl
mkdir -p "$W/state/work" "$W/state/backups-hash"
FILES=(
  2026-10-08T00-30-10.494+08-00-openclaw-backup.tar.gz
  2026-10-09T00-30-10.435+08-00-openclaw-backup.tar.gz
  2026-10-10T00-30-10.812+08-00-openclaw-backup.tar.gz
  2026-10-11T00-30-10.741+08-00-openclaw-backup.tar.gz
  2026-10-12T00-30-12.362+08-00-openclaw-backup.tar.gz
  2026-10-13T00-30-12.681+08-00-openclaw-backup.tar.gz
)
N=${#FILES[@]}
S="ssh -o BatchMode=yes -o ConnectTimeout=15"
echo "=== $(date '+%F %T') 开始两端哈希校验（$N 份） ===" >> "$LOG"
$S "$NAS" "mkdir -p ~/hash-verify" 2>/dev/null

# 1) 远端后台起算（群晖本机 CPU，不占 9p）
for f in "${FILES[@]}"; do
  qf=$(printf '%q' "$f"); qd=$(printf '%q' "$RD")
  $S "$NAS" "cd $qd && nohup sha256sum $qf > ~/hash-verify/$qf.sha256 2>&1 &" 2>/dev/null
  echo "  远端已起算: $f" >> "$LOG"
done

# 2) 本地 H 盘顺序算（受 9p 限速）
i=0
for f in "${FILES[@]}"; do
  i=$((i+1))
  if [ -s "$W/state/backups-hash/$f.sha256" ]; then
    echo "  本地已完成(缓存 $i/$N): $f" >> "$LOG"; continue
  fi
  echo "  本地计算开始 $i/$N: $f" >> "$LOG"
  sha256sum "$LD/$f" > "$W/state/backups-hash/$f.sha256" 2>>"$LOG"
  echo "  本地计算完成 $i/$N: $(cut -c1-16 "$W/state/backups-hash/$f.sha256")" >> "$LOG"
done

# 3) 等远端全部出结果
for f in "${FILES[@]}"; do
  n=0; h=""
  while [ $n -lt 480 ]; do
    h=$($S "$NAS" "cut -c1-64 ~/hash-verify/'$f'.sha256 2>/dev/null" 2>/dev/null | tr -d " \r")
    [ ${#h} -eq 64 ] && break
    sleep 15; n=$((n+1))
  done
  echo "$h" > "$W/state/backups-hash/$f.nas"
  echo "  远端结果: $f -> ${h:0:16}" >> "$LOG"
done

# 4) 比对 + 删（只删哈希一致的）
i=0
for f in "${FILES[@]}"; do
  i=$((i+1))
  lh=$(cut -c1-64 "$W/state/backups-hash/$f.sha256" 2>/dev/null)
  nh=$(tr -d " \r" < "$W/state/backups-hash/$f.nas" 2>/dev/null)
  if [ ${#lh} -eq 64 ] && [ "$lh" = "$nh" ]; then
    echo "  OK 一致 $i/$N: $f (${lh:0:16})" >> "$LOG"
    if $S "$NAS" "rm -f $RD/'$f'"; then
      echo "  DEL 已删群晖: $f" >> "$LOG"
      printf '{"ts":"%s","file":"%s","sha256":"%s","action":"deleted_nas"}' "$(date -Iseconds)" "$f" "$lh" >> "$LED"; echo >> "$LED"
    else
      echo "  WARN 删除失败: $f" >> "$LOG"
    fi
  else
    echo "  KEEP 不一致或缺哈希，保留: $f (local=${lh:0:16} nas=${nh:0:16})" >> "$LOG"
    printf '{"ts":"%s","file":"%s","action":"kept_mismatch","local":"%s","nas":"%s"}' "$(date -Iseconds)" "$f" "$lh" "$nh" >> "$LED"; echo >> "$LED"
  fi
done
echo "=== $(date '+%F %T') 完成 ===" >> "$LOG"