#!/bin/sh
# gen-recovery-doc.sh —— 备份前刷新 RECOVERY.md 的「现状」段（§8）
WS=/home/j/.openclaw/workspace
DOC=/home/j/.openclaw/RECOVERY.md
[ -f "$DOC" ] || exit 0
# 砍掉旧 §8 之后的内容
sed -n '1,/^## 8\. 现状/p' "$DOC" > /home/j/.openclaw/workspace/state/work/recovery.head
TS=$(date "+%F %T")
# L0 归档实际输出目录（2026-10-11 审查修正：create 已改为 openclaw backup create --output /mnt/d/openclaw-backups）
ARCH=$(ls -t /mnt/d/openclaw-backups/*.tar.gz /home/j/Backups/*.tar.gz 2>/dev/null | head -n 1)
ARCSZ=$(du -h "$ARCH" 2>/dev/null | cut -f1)
AG=$(ls -d /home/j/.openclaw/agents/*/ 2>/dev/null | wc -l)
WSS=$(ls -d /home/j/.openclaw/workspace-* 2>/dev/null | wc -l)
EXTRA=$(du -sh /home/j/.openclaw/backup-extra 2>/dev/null | cut -f1)
ADB=$(ls /home/j/.openclaw/backup-extra/agents-db/*.gz 2>/dev/null | wc -l)
NAS=$(ssh -o BatchMode=yes -o ConnectTimeout=8 nas "ls -1 ~/archive/jinyu/openclaw-archives/*.tar.gz 2>/dev/null | wc -l" 2>/dev/null)
{
  echo ""
  echo "- **刷新时间**：$TS"
  echo "- **最新本地归档**：$(basename "$ARCH" 2>/dev/null)（$ARCSZ，位置 $(dirname "$ARCH" 2>/dev/null)）"
  echo "- **群晖归档份数**：${NAS:-取不到}"
  echo "- **管家目录**：$AG 个 · **工作区**：$WSS 个"
  echo "- **L3 暂存**：$EXTRA（其中管家原始库 $ADB 个）"
  echo "- **密钥库**：state/openclaw.sqlite（随 L0 归档）"
} >> /home/j/.openclaw/workspace/state/work/recovery.head
mv /home/j/.openclaw/workspace/state/work/recovery.head "$DOC"
echo "RECOVERY.md 已刷新：$TS"