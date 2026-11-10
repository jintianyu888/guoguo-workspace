#!/bin/bash
# backup-selfcheck.sh —— 备份管线周度自检自查（2026-10-16 主公令）
LOG=/home/j/.openclaw/workspace/state/backup-selfcheck.log
OUT=/home/j/.openclaw/workspace/state/backup-selfcheck.md
NAS=nas
{
echo "备份管线自检 · $(date '+%F %T')"; echo
echo "1) 归档新鲜度"
NEW=$(ls -t /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | head -1)
if [ -n "$NEW" ]; then
  AGE=$(( ( $(date +%s) - $(stat -c %Y "$NEW") ) / 3600 ))
  echo "- 最新: $(basename "$NEW") · $(du -h "$NEW"|cut -f1) · ${AGE} 小时前"
  [ "$AGE" -gt 26 ] && echo "- 警告: 超26小时, 检查每日01:00任务"
else echo "- 错误: D盘无归档"; fi
echo; echo "2) 副本分布 (目标 D=1 E/H=14 群晖多份)"
echo "- D盘: $(ls /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null|wc -l) 份"
echo "- E盘: $(ls /mnt/e/openclaw-backups/*.tar.gz 2>/dev/null|wc -l) 份"
echo "- H盘: $(ls /mnt/h/openclaw-backups/*.tar.gz 2>/dev/null|wc -l) 份"
echo; echo "3) 异地(群晖)"
if timeout 12 ssh -o BatchMode=yes -o ConnectTimeout=8 "$NAS" true >/dev/null 2>&1; then echo "- 可达"; else echo "- 不可达(异地层断, 未满足3-2-1)"; fi
echo; echo "4) 明文密钥"
openclaw secrets audit 2>&1 | head -1
echo; echo "5) 磁盘"
df -h / /mnt/d /mnt/e /mnt/h 2>/dev/null | tail -4
echo; echo "6) 备份任务状态"
openclaw automations list --all 2>&1 | grep -iE "备份|归档|校验" | sed "s/  */ /g" | cut -c1-100
echo; echo "7) 优化建议"
echo "- 异地不可达 -> 修群晖SSH (当前最大风险: 单故障域)"
echo "- 明文密钥>0 -> 继续迁 SecretRef + 给备份加明文扫描门禁"
echo "- E/H<14 -> 检查保留策略是否卡在缺清单"
echo "- 长期: 改 restic/borg 增量 + 源端加密 + 密钥离线托管"
} > "$OUT" 2>&1
cat "$OUT"
