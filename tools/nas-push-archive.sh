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
if [ "$1" = "create" ]; then
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
  F=$(ls -t "$STAGE"/*.tar.gz 2>/dev/null | head -1)
  [ -z "$F" ] && { echo "原生盘无归档产物" >> "$LOG"; exit 1; }
  B=$(basename "$F"); S=$(stat -c%s "$F")
  echo "=== $(date '+%F %T') 打包完成 $B ($S 字节)，开始整文件复制到 D ===" >> "$LOG"
# 2026-11-05 22:35 主公令：第一份落 X 盘（本地最快，恢复读取优先）
mkdir -p "$XD"
if cp -f "$F" "$XD/$B.part" && mv -f "$XD/$B.part" "$XD/$B"; then
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
  cp -f "$F" "$OUT/$B.part" && mv -f "$OUT/$B.part" "$OUT/$B" || { echo "复制到 D 失败" >> "$LOG"; exit 1; }
  DS=$(stat -c%s "$OUT/$B")
  if [ "$DS" != "$S" ]; then echo "❌ D 盘大小不符 本地=$S D=$DS" >> "$LOG"; exit 1; fi
  echo "✅ 已落 D 盘: $B ($DS 字节)" >> "$LOG"
fi
  echo "=== $(date '+%F %T') 开始推新 NAS ===" >> "$LOG"
  if nas_guard "$DEST"; then
    AV=$(df -Pk "$DEST" | awk 'NR==2{print $4*1024}')
    if [ "${AV:-0}" -lt "$S" ]; then
      echo "❌ 新 NAS 空间不足：剩余 ${AV:-0} 字节，需要 $S 字节 —— 跳过推送，本地归档保留" >> "$LOG"
    else
      cp -f "$F" "$DEST/$B.part" && mv -f "$DEST/$B.part" "$DEST/$B"
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
  F=$(ls -t "$OUT"/*.tar.gz 2>/dev/null | head -1)
  [ -z "$F" ] && { echo "无归档可推送"; exit 1; }
  B=$(basename "$F"); S=$(stat -c%s "$F")
  nas_guard "$DEST" || { echo "❌ 新 NAS 未挂载，拒绝推送"; exit 1; }
  AV=$(df -Pk "$DEST" | awk 'NR==2{print $4*1024}')
  if [ "${AV:-0}" -lt "$S" ]; then echo "❌ 新 NAS 空间不足：剩余 ${AV:-0} 字节，需要 $S 字节"; exit 1; fi
  cp -f "$F" "$DEST/$B.part" && mv -f "$DEST/$B.part" "$DEST/$B"
  R=$(stat -c%s "$DEST/$B" 2>/dev/null)
  if [ "$S" = "$R" ]; then echo "✅ 归档已推送到新 NAS: $B"; else echo "❌ 大小不符 本地=$S 目标=${R:-0}"; fi
fi
