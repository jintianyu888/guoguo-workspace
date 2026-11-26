#!/bin/bash
# nas-push-archive.sh —— A 方案版（2026-10-18 主公拍板）
# 变更：先打包到 WSL 原生 ext4（快），再整文件复制到 Windows 盘（9p 82MB/s），最后推群晖
# 2026-11-02 主公令：老 NAS 断联，改推已挂载的新 NAS（//192.168.1.109/home → /mnt/nas）
# 新 NAS 的 SSH 22 关闭，只能走本地挂载路径；路径真源见 tools/nas-config.sh
. /home/j/.openclaw/workspace/tools/nas-config.sh
export OC_SQLITE_PROBE_TIMEOUT_MS="${OC_SQLITE_PROBE_TIMEOUT_MS:-180000}"
DEST="$NAS_ARCHIVES"
OUT=/mnt/d/openclaw-backups
XD=/mnt/x/openclaw-backups
STAGE=/home/j/backup-stage  # 2026-10-18 修：不可放在 /home/j/.openclaw 内（backup create 禁止写入源路径）
LOG=/home/j/.openclaw/workspace/state/work/bk-run.log
mkdir -p "$OUT" "$STAGE"
# 2026-11-15 修（#1001）：退出兜底清理暂存——超时/被杀也会执行，前提是 X 盘已有同尺寸副本
cleanup_stage() {
  [ -n "${F:-}" ] || return 0
  case "$F" in "$STAGE"/*) ;; *) return 0 ;; esac
  [ -f "$F" ] || return 0
  local xb="$XD/$(basename "$F")"
  if [ -f "$xb" ] && [ "$(stat -c %s "$xb" 2>/dev/null)" = "${S:-0}" ]; then
    rm -f "$F"
    echo "=== $(date '+%F %T') 兜底清理暂存 $(basename "$F") ===" >> "$LOG"
  fi
}
trap cleanup_stage EXIT
if [ "$1" = "create" ]; then
  # 2026-11-15 修（#1001）：重试去重——今日已有归档（<12h 且 >10G）就不再重新打包
  TODAY=$(date +%Y-%m-%d)
  DUPF=$(ls -t "$XD"/*"$TODAY"*.tar.gz "$OUT"/*"$TODAY"*.tar.gz 2>/dev/null | while read -r cand; do
    [ -f "$cand" ] || continue
    csz=$(stat -c %s "$cand" 2>/dev/null || echo 0)
    cmt=$(stat -c %Y "$cand" 2>/dev/null || echo 0)
    [ "$csz" -gt 10737418240 ] && [ $(( $(date +%s) - cmt )) -lt 43200 ] && { echo "$cand"; break; }
  done | head -1)
  if [ -n "${DUPF:-}" ] && [ "${FORCE_PACK:-0}" != "1" ]; then
    echo "=== $(date '+%F %T') 今日已有归档 $(basename "$DUPF")，跳过重复打包（仍执行落盘/推送） ===" >> "$LOG"
    SKIP=1
  else
    SKIP=0
  fi

  if [ "$SKIP" = "0" ]; then
  sh /home/j/.openclaw/workspace/tools/stage-agent-dbs.sh >> "$LOG" 2>&1
  sh /home/j/.openclaw/workspace/tools/gen-recovery-doc.sh >> "$LOG" 2>&1
  sh /home/j/.openclaw/workspace/tools/backup-report.sh > /home/j/.openclaw/workspace/state/backup-report.txt 2>&1
  echo "=== $(date '+%F %T') 开始在原生盘打包 ===" >> "$LOG"
  # 2026-11-06 告警修复：sqlite 头探测 10s 硬超时，慢盘/冷缓存下会误杀整次备份 → 有界重试 3 次
  BAK_OK=0
  for i in 1 2 3; do
    TRY="$STAGE/.try$i"; rm -rf "$TRY"; mkdir -p "$TRY"
    echo "=== $(date '+%F %T') openclaw backup 尝试 $i/3 ===" >> "$LOG"
    if openclaw backup create --output "$TRY" --verify >> "$LOG" 2>&1; then
      mv -f "$TRY"/*.tar.gz "$STAGE"/ 2>/dev/null
      rm -rf "$TRY"; BAK_OK=1; break
    fi
    echo "=== $(date '+%F %T') 尝试 $i 失败，清理后重试 ===" >> "$LOG"
    rm -rf "$TRY"; sleep 20
  done
  [ "$BAK_OK" = "1" ] || { echo "=== $(date '+%F %T') 打包连续 3 次失败 ===" >> "$LOG"; echo "打包失败" >> "$LOG"; exit 1; }
  fi
  if [ "$SKIP" = "1" ]; then F="$DUPF"; else F=$(ls -t "$STAGE"/*.tar.gz 2>/dev/null | head -1); fi
  [ -z "$F" ] && { echo "原生盘无归档产物" >> "$LOG"; exit 1; }
  B=$(basename "$F"); S=$(stat -c%s "$F")
  if [ -f "$DEST/$B" ] && [ "$(stat -c%s "$DEST/$B" 2>/dev/null)" = "$S" ]; then echo "✅ 新 NAS 已有同大小副本，跳过: $B" | tee -a "$LOG"; exit 0; fi
  if [ "${NP_DRY:-0}" = "1" ]; then echo "[dry] 将落盘 X/D 并推 NAS: $B ($S 字节)"; exit 0; fi
  echo "=== $(date '+%F %T') 打包完成 $B ($S 字节)，开始整文件复制到 D ===" >> "$LOG"
# 2026-11-05 22:35 主公令：第一份落 X 盘（本地最快，恢复读取优先）
mkdir -p "$XD"
if [ "$F" = "$XD/$B" ]; then echo "✅ 已在 X 盘(源即副本): $XD/$B" >> "$LOG"; elif cp -f "$F" "$XD/$B.part" && mv -f "$XD/$B.part" "$XD/$B"; then
  XS=$(stat -c %s "$XD/$B" 2>/dev/null || echo 0)
  if [ "$XS" = "$(stat -c %s "$F")" ]; then echo "✅ 已落 X 盘(第一份): $XD/$B ($XS 字节)" >> "$LOG";
  else echo "❌ X 盘大小不符: $XS 与源不符" >> "$LOG"; exit 1; fi
else echo "❌ 复制到 X 失败" >> "$LOG"; exit 1; fi
  # 2026-11-05 22:46 主公令：X 为第一层，D 降为次级；空间不足只告警不阻断后续推送
  DNEED=$((S/1024 + 2097152))
  DFREE=$(df -Pk /mnt/d 2>/dev/null | sed -n 2p | tr -s " " | cut -d" " -f4)
  [ -z "$DFREE" ] && DFREE=0
  if [ "$DFREE" -lt "$DNEED" ]; then
    echo "⚠️ D 盘空间不足（余 $DFREE KB，需 $DNEED KB）——跳过 D，X/群晖/E/H 继续" >> "$LOG"
    SKIPD=1
  else
    SKIPD=0
  fi
  if [ "$SKIPD" = "0" ]; then
  # 2026-11-26：cp 一次性复制在 9p 上会中途断（11-26 03:18 就是这条把整条链 abort）。
  # 改 rsync 续传 + 3 次重试；失败保留 .part 待次日续传，且不再阻断群晖/E/H 推送。
  DOK=0
  for _i in 1 2 3; do
    timeout 7200 rsync -a --partial --append-verify --inplace "$F" "$OUT/$B.part" >>"$LOG" 2>&1
    RS=$(stat -c %s "$OUT/$B.part" 2>/dev/null || echo 0)
    if [ "$RS" = "$S" ]; then mv -f "$OUT/$B.part" "$OUT/$B"; DOK=1; break; fi
    echo "=== $(date '+%F %T') D 复制第 $_i 次未完成（$RS/$S 字节），5 秒后续传 ===" >> "$LOG"
    sleep 5
  done
  if [ "$DOK" != "1" ]; then
    echo "❌ $(date '+%F %T') 复制到 D 失败（rsync 3 次未完成；余 $DFREE KB 需 $DNEED KB），保留 .part 待续传；继续 X/群晖/E/H" >> "$LOG"
  fi
  DS=$(stat -c%s "$OUT/$B")
  if [ "$DS" != "$S" ]; then echo "❌ D 盘大小不符 本地=$S D=$DS" >> "$LOG"; exit 1; fi
  echo "✅ 已落 D 盘: $B ($DS 字节)" >> "$LOG"
fi
  if [ "${NP_ASYNC:-1}" = "1" ]; then
    systemd-run --user --collect --unit="nas-push-$(date +%H%M%S)" --setenv=PATH=/usr/bin:/bin /bin/bash "$0" push "$F" >> "$LOG" 2>&1 \
      && echo "=== $(date '+%F %T') 已异步派发 NAS 推送 $(basename "$F")（不占备份窗口）" >> "$LOG" \
      || echo "⚠️ $(date '+%F %T') 异步派发失败，本次跳过 NAS（下次 push 补推）" >> "$LOG"
    bash /home/j/.openclaw/workspace/tools/backup-retain.sh >> "$LOG" 2>&1
    exit 0
  fi
  echo "=== $(date '+%F %T') 开始推新 NAS ===" >> "$LOG"
  if nas_guard "$DEST"; then
    AV=$(df -Pk "$DEST" | awk 'NR==2{print $4*1024}')
    if [ "${AV:-0}" -lt "$S" ]; then
      echo "❌ 新 NAS 空间不足：剩余 ${AV:-0} 字节，需要 $S 字节 —— 跳过推送，本地归档保留" >> "$LOG"
    else
      rsync -a --partial --inplace --append-verify "$F" "$DEST/$B.part" && mv -f "$DEST/$B.part" "$DEST/$B"
      R=$(stat -c%s "$DEST/$B" 2>/dev/null)
      if [ "$S" = "$R" ]; then
        echo "✅ 归档已推送到新 NAS: $B ($S 字节)" >> "$LOG"
      else
        echo "❌ 大小不符 本地=$S 目标=${R:-0}" >> "$LOG"
      fi
    fi
  else
    echo "⚠️ 新 NAS 未挂载/no nas_guard：跳过推送，本地归档保留" >> "$LOG"
  fi
  echo "=== $(date '+%F %T') 收尾：保留策略 ===" >> "$LOG"
  bash /home/j/.openclaw/workspace/tools/backup-retain.sh >> "$LOG" 2>&1
  echo "=== $(date '+%F %T') 完成，清理暂存 ===" >> "$LOG"
  rm -f "$STAGE"/*.tar.gz 2>/dev/null
fi
if [ "$1" = "push" ]; then
  F=${2:-$(ls -t "$OUT"/*.tar.gz 2>/dev/null | head -1)}
  [ -z "$F" ] && { echo "无归档可推送" >> "$LOG"; exit 1; }
  [ -f "$F" ] || { echo "❌ 源归档不存在: $F" >> "$LOG"; exit 1; }
  B=$(basename "$F"); S=$(stat -c%s "$F")
  if [ -f "$DEST/$B" ] && [ "$(stat -c%s "$DEST/$B" 2>/dev/null)" = "$S" ]; then echo "✅ 新 NAS 已有同大小副本，跳过: $B" | tee -a "$LOG"; exit 0; fi
  nas_guard "$DEST" || { echo "❌ 新 NAS 未挂载，拒绝推送" >> "$LOG"; exit 1; }
  AV=$(df -Pk "$DEST" | awk 'NR==2{print $4*1024}')
  if [ "${AV:-0}" -lt "$S" ]; then echo "❌ 新 NAS 空间不足：剩余 ${AV:-0} 字节，需要 $S 字节" >> "$LOG"; exit 1; fi
  ok=0; R=0
  if [ "${NP_FORCE_SSH:-0}" != "1" ]; then
    rm -f "$DEST/$B.part"
    if cp -f "$F" "$DEST/$B.part" && mv -f "$DEST/$B.part" "$DEST/$B"; then
      R=$(stat -c%s "$DEST/$B" 2>/dev/null)
      [ "$S" = "$R" ] && ok=1
    fi
    [ "$ok" = "1" ] || rm -f "$DEST/$B.part" 2>/dev/null
  fi
  if [ "$ok" != "1" ]; then
    echo "⚠️ $(date '+%F %T') CIFS 推送失败/跳过（本地=$S），改用 SSH/cat: $B" >> "$LOG"
    RD="${NAS_SSH_ARCHIVES:-/volume1/homes/guoguonas/archive/jinyu/openclaw-archives}"
    if timeout 7200 ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=30 -o ServerAliveCountMax=10 nas "cat > '$RD/$B.part'" < "$F"; then
      R=$(timeout 60 ssh -o BatchMode=yes nas "stat -c%s '$RD/$B.part'" 2>/dev/null | tr -d '
')
      if [ "$S" = "$R" ]; then
        timeout 60 ssh -o BatchMode=yes nas "mv -f '$RD/$B.part' '$RD/$B'" && ok=1
      fi
    fi
    [ "$ok" = "1" ] || timeout 30 ssh -o BatchMode=yes nas "rm -f '$RD/$B.part'" 2>/dev/null || true
  fi
  if [ "$ok" = "1" ]; then
    echo "✅ 归档已推送到新 NAS: $B ($S 字节)" | tee -a "$LOG"
    exit 0
  fi
  echo "❌ 归档推送失败（CIFS 与 SSH 均失败）: $B 本地=$S 目标=${R:-0}" | tee -a "$LOG" >&2
  exit 1
fi
