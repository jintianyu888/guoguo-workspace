#!/usr/bin/env bash
# align-backup-triple.sh v2 —— 三地归档「并集拉齐」（只补不删）
# v1 2026-10-03：D/E/H 互查拉齐。
# v2 2026-11-25（双审 qwen3.8-max 准予 + glm-5.4 修改意见全采纳）：
#   ① 源候选加 X 盘（主公 2026-11-05 令 X 为第一层），X 优先、D/E/H 兜底；NAS 不作源。
#   ② 复制改 cp → *.part → mv 原子落名，大小不符不落名。
#   ③ 目标盘可用 < 源+2GiB 时跳过该盘（不阻断其他盘，与 nas-push 2026-11-05 口径一致）。
#   ④ 执行前清历史 .part 残留；复制失败即删 .part 保空间（证据进日志）。
#   ⑤ 硬截止 ALIGN_DEADLINE（默认次日 00:30，防撞 01:00 全量备份）。
#   ⑥ 串行复制，避免带宽争抢；ALIGN_DRY=1 只打印不拷贝。
set -u
export PATH=/home/j/.npm-global/bin:/usr/bin:/bin
W=/home/j/.openclaw/workspace
LOG=$W/state/work/align-triple.log
DIRS='d e h'
XDIR=/mnt/x/openclaw-backups
DRY=${ALIGN_DRY:-0}
say(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }

# 硬截止：默认次日 00:30（防撞 01:00 全量备份）
if [ -n "${ALIGN_DEADLINE:-}" ]; then DL=$ALIGN_DEADLINE; else DL=$(date -d 'tomorrow 00:30' +%s); fi
say "== v2 开始 dry=$DRY 硬截止=$(date -d @$DL '+%F %T') =="

# 0) 预清历史 .part 残留（>30 分钟的旧半份）
for d in $DIRS; do
  for p in /mnt/$d/openclaw-backups/*.part; do
    [ -f "$p" ] || continue
    if [ $(( $(date +%s) - $(stat -c %Y "$p") )) -gt 1800 ]; then
      say "清理残留 .part: $p ($(stat -c %s "$p") 字节)"
      [ "$DRY" = "0" ] && rm -f "$p"
    fi
  done
done

# 1) 源稳定性预检：X 在写（最新归档 mtime <120s）则本轮弃用 X 源
X_BUSY=0
if [ -d "$XDIR" ]; then
  NEWEST_X=$(ls -t $XDIR/*.tar.gz 2>/dev/null | head -1)
  if [ -n "$NEWEST_X" ] && [ $(( $(date +%s) - $(stat -c %Y "$NEWEST_X") )) -lt 120 ]; then
    X_BUSY=1; say "⚠️ X 最新归档 2 分钟内有写入，本轮 X 降为不可用源"
  fi
fi

# 2) 并集：X + D/E/H（v1 只扫 D/E/H）；ALIGN_ONLY=文件名(逗号分隔) 时只处理指定档
T=$(mktemp)
{ [ "$X_BUSY" = "0" ] && ls $XDIR/*.tar.gz 2>/dev/null; for d in $DIRS; do ls /mnt/$d/openclaw-backups/*.tar.gz 2>/dev/null; done; } \
  | xargs -n1 basename 2>/dev/null | sort -u > "$T"
if [ -n "${ALIGN_ONLY:-}" ]; then
  : > "$T.f"
  IFS=',' read -ra _only <<< "$ALIGN_ONLY"
  for _f in "${_only[@]}"; do grep -Fx "$_f" "$T" >> "$T.f" 2>/dev/null; done
  mv -f "$T.f" "$T"
  say "ALIGN_ONLY 生效: ${#_only[@]} 个指定档"
fi
say "并集文件数: $(wc -l < "$T")"

SKIP_ALL=0
while read -r f; do
  [ -n "$f" ] || continue
  [ "$SKIP_ALL" = "1" ] && { say "硬截止跳过: $f"; continue; }
  SRC=""
  [ "$X_BUSY" = "0" ] && [ -f "$XDIR/$f" ] && SRC="$XDIR/$f"
  [ -z "$SRC" ] && for x in $DIRS; do [ -f "/mnt/$x/openclaw-backups/$f" ] && { SRC="/mnt/$x/openclaw-backups/$f"; break; }; done
  if [ -z "$SRC" ]; then say "  ⚠ 无源: $f"; continue; fi
  S=$(stat -c %s "$SRC")
  for d in $DIRS; do
    [ "$SKIP_ALL" = "1" ] && break
    DST="/mnt/$d/openclaw-backups/$f"
    [ -f "$DST" ] && continue
    [ -f "$DST.part" ] && { say "  ⚠ $d 已有 .part 在写，跳过: $f"; continue; }
    if [ $(date +%s) -ge "$DL" ]; then say "⏰ 硬截止到达，停止补拷（剩 $f → $d 起）"; SKIP_ALL=1; break; fi
    AVAIL=$(df -B1 /mnt/$d 2>/dev/null | sed -n 2p | tr -s ' ' | cut -d' ' -f4); AVAIL=${AVAIL:-0}
    NEED=$(( S + 2147483648 ))
    if [ "$AVAIL" -lt "$NEED" ]; then say "  ⚠ $d 空间不足(余 $AVAIL B 需 $NEED B)，跳过: $f"; continue; fi
    if [ "$DRY" = "1" ]; then say "  [dry] $d 将补 $f ($S 字节, 源=$SRC)"; continue; fi
    t0=$(date +%s)
    if cp -f "$SRC" "$DST.part"; then
      DS=$(stat -c %s "$DST.part" 2>/dev/null || echo 0)
      if [ "$DS" = "$S" ]; then
        mv -f "$DST.part" "$DST"
        say "  → $d 补 $f ($DS 字节, 耗时 $(( $(date +%s) - t0 ))s, 源=$SRC)"
      else
        say "  ❌ $d 大小不符 $DS 不等 $S，删 .part: $f"
        rm -f "$DST.part"
      fi
    else
      RC=$?
      say "  ❌ $d 复制失败 $f (cp rc=$RC)，删 .part 保留空间"
      rm -f "$DST.part"
    fi
  done
done < "$T"
rm -f "$T"

# 3) 汇总 + 后验（真跑时用既有 backup-copy-verify.py 抽样哈希复验 D/E/H 一致性）
for d in $DIRS; do say "  $d: $(ls /mnt/$d/openclaw-backups/*.tar.gz 2>/dev/null | wc -l) 个归档"; done
if [ "$DRY" = "0" ]; then
  say "后验: backup-copy-verify.py"
  timeout 900 python3 $W/tools/backup-copy-verify.py >> "$LOG" 2>&1 || say "  ⚠ 后验工具异常(不阻断，人工复核)"
fi
say "== v2 结束 =="
