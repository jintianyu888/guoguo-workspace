#!/bin/bash
# backup-tier1-critical.sh —— T1 重点数据（每天 2 次：08:00 / 20:00）
# 内容：配置 + 密钥仓 + 台账（小、快、高频）
set -u
# 等空闲守卫（2026-10-02 主公令）：有其他备份/重活在跑就先等（flock 串行）
. /home/j/.openclaw/workspace/tools/backup-wait-idle.sh
. /home/j/.openclaw/workspace/tools/nas-config.sh
TS=$(date +%Y%m%d-%H%M)
W=/home/j/.openclaw/workspace
OUT=/mnt/e/openclaw-backups/tier1
LOG=$W/state/work/tier1.log
mkdir -p "$OUT"
echo "== $TS T1 重点备份 ==" >> "$LOG"
# 打包：配置 + 密钥仓 + 全部台账
# 打包：配置 + 密钥仓 + 全部台账 + 文档（含 问题库/经验库 —— 2026-10-02 纳入）
tar czf "$OUT/tier1-$TS.tar.gz" --exclude='*state/dl' --exclude='*/state/tmp' -C /home/j   .openclaw/openclaw.json   .openclaw/state/openclaw.sqlite   .openclaw/workspace/state   .openclaw/workspace/docs 2>/dev/null
S1=$(du -h "$OUT/tier1-$TS.tar.gz" 2>/dev/null | cut -f1)
# 2026-11-07 主公批准 #155：含明文凭据，打包后立即加密（gpg 对称 AES256）
KEY=/home/j/.openclaw/secrets-in/t1.key
if [ -s "$KEY" ] && command -v gpg >/dev/null 2>&1; then
  if gpg --batch --yes --quiet --passphrase-file "$KEY" --cipher-algo AES256 -c "$OUT/tier1-$TS.tar.gz" 2>>"$LOG"; then
    rm -f "$OUT/tier1-$TS.tar.gz"
    echo "  加密: tier1-$TS.tar.gz.gpg" >> "$LOG"
  else
    echo "  ⚠️ 加密失败，保留明文包（需人工处理）" >> "$LOG"
  fi
else
  echo "  ⚠️ 未找到密钥 $KEY，本次仍为明文包" >> "$LOG"
fi
echo "  本地: tier1-$TS.tar.gz ($S1)" >> "$LOG"
# 推群晖（小，直接推）
# 推新 NAS（2026-11-02 老 NAS 断联；新 NAS SSH 关闭，走挂载路径）
if nas_guard "$NAS_TIER1"; then
  cp -f "$OUT/tier1-$TS.tar.gz" "$NAS_TIER1/" 2>>"$LOG" && echo "  ✅ 已推新 NAS" >> "$LOG" || echo "  ⚠️ 新 NAS 推送失败" >> "$LOG"
else
  echo "  ⚠️ 新 NAS 未挂载，跳过 tier1 推送（本地已保留）" >> "$LOG"
fi
# 保留最近 30 份（约 15 天）
ls -t "$OUT"/tier1-*.tar.gz.gpg "$OUT"/tier1-*.tar.gz 2>/dev/null | tail -n +31 | xargs -r rm -f
echo "  保留: $(ls "$OUT"/tier1-*.tar.gz 2>/dev/null|wc -l) 份" >> "$LOG"
# 2026-10-03 补（昨晚审计建议③）：用户级配置小备份（.npmrc/.gitconfig/.bashrc/.profile/.ssh 配置）
bash /home/j/.openclaw/workspace/tools/backup-user-config.sh >> "$LOG" 2>&1 || echo "  ⚠️ 用户级配置备份失败" >> "$LOG"
