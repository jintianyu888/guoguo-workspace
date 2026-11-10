#!/bin/bash
# daily-backup.sh —— 每日全量备份（网关命令型任务执行，2026-10-15 重写）
# 背景：旧版由 agent 会话 setsid 甩出后台，被本机掐掉 → 42 小时没出新归档
set -u
OUT=/mnt/d/openclaw-backups
LOG=/home/j/.openclaw/workspace/state/work/bk-run.log
mkdir -p "$OUT"
echo "=== [$(date '+%F %T')] 每日全量备份开始 ===" | tee -a "$LOG"
echo "[1/5] 暂存管家原始库..." | tee -a "$LOG"; sh /home/j/.openclaw/workspace/tools/stage-agent-dbs.sh >>"$LOG" 2>&1 || true
echo "[2/5] 刷新自恢复手册..." | tee -a "$LOG"; sh /home/j/.openclaw/workspace/tools/gen-recovery-doc.sh >>"$LOG" 2>&1 || true
echo "[3/5] 刷新备份状态报告..." | tee -a "$LOG"; sh /home/j/.openclaw/workspace/tools/backup-report.sh > /home/j/.openclaw/workspace/state/backup-report.txt 2>&1 || true
echo "[4/5] 生成全量归档(约 60 分钟)..." | tee -a "$LOG"
# 2026-11-04 修复：backup CLI 的 SQLite 头探测内建 10s 硬超时，要扫 ~47 万条目，
# 凌晨冷缓存 + 网关 cgroup 节流下必然超线（实测暖缓存 6.9s）。只做预热，不做重试（三审结论：重试会把已知失败静默转成成功）。
echo "[4/5-prewarm] 预热 SQLite 元数据缓存..." | tee -a "$LOG"
find /home/j/.openclaw -xdev \( -name '*.db' -o -name '*.sqlite*' \) 2>/dev/null | head -2000 | xargs -r -n50 head -c 16 >/dev/null 2>&1 || true
openclaw backup create --output "$OUT" --verify >>"$LOG" 2>&1
RC=$?
F=$(ls -t "$OUT"/*.tar.gz 2>/dev/null | head -1)
echo "[4/5] rc=$RC 归档=$(basename "$F" 2>/dev/null) 大小=$(du -h "$F" 2>/dev/null | cut -f1)" | tee -a "$LOG"
# ① 2026-10-16 主公令：归档后【只记 名称+大小】（秒级，不拖慢备份）；哈希留到闲时任务算
echo "[4.5/5] 登记归档名称+大小(①)..." | tee -a "$LOG"
NEW=$(ls -t /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | head -1)
if [ -n "$NEW" ]; then
  NB=$(basename "$NEW"); NS=$(stat -c%s "$NEW")
  M=/mnt/d/openclaw-backups/ARCHIVE-MANIFEST.tsv
  {
    printf '%s\t%s\t%s\n' "$(date '+%F %T')" "$NB" "$NS"
    for X in /mnt/e/openclaw-backups /mnt/h/openclaw-backups; do
      if [ -f "$X/$NB" ]; then printf '%s\t%s\t%s\n' "$(date '+%F %T')" "$NB(副本:$X)" "$(stat -c%s "$X/$NB")"; fi
    done
  } >> "$M"
  echo "  已登记: $NB ($NS 字节)" | tee -a "$LOG"
  echo "  待闲时算哈希: sh tools/backup-hash.sh write-latest /mnt/d/openclaw-backups /mnt/e/openclaw-backups /mnt/h/openclaw-backups" >>"$LOG"
fi
# [5/5] 保留策略已拆到 02:30「归档哈希+保留」任务（2026-10-16 主公令：哈希确认后再删）
echo "[5/5] 保留策略改由 02:30 闲时任务执行（此处不再跑）" | tee -a "$LOG"
echo "=== [$(date '+%F %T')] 完成 rc=$RC ===" | tee -a "$LOG"
exit $RC
