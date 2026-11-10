#!/bin/bash
# pre-upgrade-backup.sh —— 重大升级/变更前的即时全量备份（2026-10-15 主公令）
# 用法: pre-upgrade-backup.sh "升级说明"
WHY="${1:-未说明}"
LOG=/home/j/.openclaw/workspace/state/work/pre-upgrade-backup.log
OUT=/mnt/e/openclaw-backups   # 2026-11-02 主公令：D 盘不再放备份（升级前备份落 E）
echo "[$(date '+%F %T')] 升级前备份开始：$WHY" >> "$LOG"
sh /home/j/.openclaw/workspace/tools/gen-recovery-doc.sh >> "$LOG" 2>&1
openclaw backup create --output "$OUT" --verify >> "$LOG" 2>&1
RC=$?
F=$(ls -t "$OUT"/*.tar.gz 2>/dev/null | head -1)
echo "[$(date '+%F %T')] rc=$RC 最新归档: $(basename "$F" 2>/dev/null)" >> "$LOG"
if [ "$RC" = "0" ] && [ -n "$F" ]; then
  # 2026-10-23 双审修复：再建一条 hardlink 进 predanger 专用目录（同盘零成本）；2026-11-02 起主目录改 E，hardlink 仍在同盘成立
  PL=/mnt/e/openclaw-predanger/predanger-$(basename "$F")
  mkdir -p /mnt/e/openclaw-predanger || { echo "[$(date '+%F %T')] ERROR predanger 目录创建失败，禁止继续" >> "$LOG"; exit 1; }
  # 2026-11-02 双审补充：确认同文件系统（防挂载回落导致 hardlink 退化成失败/跨盘）
  if [ "$(stat -c %d "$OUT" 2>/dev/null)" != "$(stat -c %d /mnt/e/openclaw-predanger 2>/dev/null)" ]; then
    echo "[$(date '+%F %T')] ERROR OUT 与 predanger 不在同一文件系统（dev 不一致），hardlink 会失败" >> "$LOG"; exit 1
  fi
  if ln -f "$F" "$PL" 2>/dev/null; then
    if [ "$(stat -c %i "$F" 2>/dev/null)" != "$(stat -c %i "$PL" 2>/dev/null)" ]; then
      echo "[$(date '+%F %T')] WARN hardlink inode 不一致，predanger 可能是独立副本: $(basename "$PL")" >> "$LOG"
    fi
    echo "[$(date '+%F %T')] predanger hardlink 已建: $(basename "$PL") (links=$(stat -c %h "$PL" 2>/dev/null))" >> "$LOG"
    printf '{"ts":"%s","reason":"pre-upgrade:%s","file":"%s","bytes":%s,"kind":"hardlink"}
' "$(date -Is)" "$WHY" "$(basename "$PL")" "$(stat -c %s "$F")" >> /home/j/.openclaw/workspace/state/predanger-ledger.jsonl
  else
    echo "[$(date '+%F %T')] WARN predanger hardlink 失败" >> "$LOG"
  fi
  echo "✅ 升级前备份完成: $(basename "$F") ($(du -h "$F" | cut -f1)) —— 可以继续升级"
else
  echo "❌ 升级前备份失败 (rc=$RC) —— 禁止继续升级，先排查"
  exit 1
fi
