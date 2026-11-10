#!/bin/bash
# secure-cloud-backup.sh v3 —— 周档加密上传百度网盘 + 密码邮件（一档一密）
# v2 修正：先暂存后整体移入，避免上传半成品
# v3 修正：① 加密后自检解密 ② 密码先落本地托管，邮件全成功才销毁 ③ 失败推飞书 ④ 上传残留检测
set -uo pipefail
umask 077
W=/home/j/.openclaw/workspace
CLOUD=/mnt/e/openclaw-cloud-backup/备份归档-加密
STAGEROOT=/mnt/e/openclaw-store/.cloud-stage
ESCROW=/home/j/.cloud-escrow
LED=$W/state/cloud-backup-ledger.jsonl
LOG=$W/state/work/cloud-backup.log
LOCK=$W/state/work/cloud-backup.lock
mkdir -p "$CLOUD" "$STAGEROOT" "$ESCROW" "$W/state/work"; chmod 700 "$ESCROW"
exec 9>"$LOCK"; flock -n 9 || { echo "SKIP 已有实例在跑"; exit 0; }
log(){ echo "[$(date "+%F %T")] $*" | tee -a "$LOG"; }
alert(){ bash "$W/tools/notify.sh" "$1" >/dev/null 2>&1 || true; }
FF=""; DRY=0; MAIL=1
while [ $# -gt 0 ]; do case "$1" in
  --archive) FF="$2"; shift;;
  --dry) DRY=1;;
  --no-mail) MAIL=0;;
esac; shift; done
if [ -z "$FF" ]; then FF=$(ls -t /mnt/d/openclaw-backups/*openclaw-backup.tar.gz 2>/dev/null | head -1); fi
[ -z "$FF" ] || [ ! -f "$FF" ] && { log "❌ 找不到归档"; alert "❌ 云端加密备份失败：找不到归档"; exit 1; }
BASE=$(basename "$FF"); SZ=$(stat -c %s "$FF")
log "🔐 开始加密：$BASE ($SZ 字节)"
PW=$(openssl rand -base64 24 | tr -dc "A-Za-z0-9" | cut -c1-24)
OUT=$CLOUD/$BASE
STAGE=$STAGEROOT/$BASE
PWFILE=$ESCROW/$BASE.pw
printf '%s' "$PW" > "$PWFILE"; chmod 600 "$PWFILE"
if [ "$DRY" = "1" ]; then log "[演练] 暂存 $STAGE → 完成后移入 $OUT；24位密码、10GB分片、2封邮件"; exit 0; fi
rm -rf "$STAGE" "$OUT"; mkdir -p "$STAGE"
trap 'log "⏹ 收到中断信号：清理暂存 $STAGE（产物目录 $CLOUD 绝不动）"; shred -u "${PWFILE:-/nonexistent}" 2>/dev/null || true; rm -rf "$STAGE"; exit 143' INT TERM
trap 'rc=$?; if [ "$rc" -ne 0 ]; then shred -u "${PWFILE:-/nonexistent}" 2>/dev/null || rm -f "${PWFILE:-/nonexistent}"; fi' EXIT
read -r AVD < <(df -BG --output=avail /mnt/e | tail -1 | tr -dc "0-9")
if [ "${AVD:-0}" -lt 60 ]; then log "❌ E 盘剩余 ${AVD}G < 60G，中止"; alert "❌ 云端加密备份中止：E 盘仅剩 ${AVD}G"; exit 1; fi
T0=$(date +%s)
# 2026-10-24 双审修订（v4-pro+kimi 共识）：改成「流式加密→直接分片」
# 原实现先写 23.7GB .enc 到 9p 再 split，单步按小时计且被外部掐掉（10-22 三次无完成记录）
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -in "$FF" -pass file:"$PWFILE" 2>>"$LOG" | split -b 10G -d -a 2 - "$STAGE/$BASE.enc.part" || { log "❌ 加密/分片失败"; alert "❌ 云端加密备份失败：加密或分片步骤"; exit 1; }
T1=$(date +%s)
# 自检：解密头部 1MB 与原文比对，确认这份密码真的能解
head -c 1048576 "$FF" > "$STAGE/.src.head"
head -c 1048624 "$STAGE/$BASE.enc.part00" | openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass file:"$PWFILE" 2>/dev/null | head -c 1048576 > "$STAGE/.dec.head"
if cmp -s "$STAGE/.src.head" "$STAGE/.dec.head"; then log "🔎 自检通过：用该密码可正确解密"; else log "❌ 自检失败：加密产物无法解密"; alert "❌ 云端加密备份失败：解密自检不通过"; rm -rf "$STAGE"; exit 1; fi
rm -f "$STAGE/.src.head" "$STAGE/.dec.head"
# 口令已在加密前写入 $PWFILE（2026-10-24 双审：提前落 escrow，9p 上 chmod 不可靠；.pw 绝不可放 $STAGE）
# 分片已在加密管道内完成（见上），此处不再二次 split
PARTS=$(ls "$STAGE"/*.enc.part* 2>/dev/null | wc -l)
ENC_SHA=$(cat "$STAGE"/*.enc.part* | sha256sum | awk "{print \$1}")
printf "{\"archive\":\"%s\",\"src_size\":%s,\"parts\":%s,\"enc_sha256\":\"%s\",\"created\":\"%s\"}\n" "$BASE" "$SZ" "$PARTS" "$ENC_SHA" "$(date -Iseconds)" > "$STAGE/manifest.json"
log "✅ 加密完成：$PARTS 片，用时 $((T1-T0))s；移入同步目录"
mkdir -p "$OUT" && mv "$STAGE"/* "$OUT"/ && rmdir "$STAGE" || { log "❌ 移入失败，产物在 $STAGE"; alert "❌ 云端加密备份：移入同步目录失败"; exit 1; }
MRC=0
if [ "$MAIL" = "1" ]; then
  set -a; . "$W/tools/cloud-mail.env"; set +a
  BODY=$(printf "备份加密密码\n\n归档：%s\n大小：%s 字节\n分片：%s 片（10GB/片）\n加密：AES-256-CBC，PBKDF2 20万次\n密码：%s\n\n解密：\n  cat %s.enc.part* > x.enc\n  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in x.enc -out 原归档.tar.gz -pass pass:<见上方密码>" "$BASE" "$SZ" "$PARTS" "$PW" "$BASE" "$PW" "$ENC_SHA")
  RAW=$(openclaw secrets store get SMTP_163_AUTH 2>/dev/null); SMTPPASS=${RAW#SMTP_163_AUTH=}
  for RCPT in "$RECIPIENT_A" "$RECIPIENT_B"; do
    SMTP_HOST="$SMTP_HOST" SMTP_PORT="$SMTP_PORT" SMTP_USER="$MAIL_FROM" SMTP_PASS="$SMTPPASS" \
      python3 "$W/tools/send-mail.py" --to "$RCPT" --subject "备份密码｜$BASE" --body "$BODY" 2>>"$LOG" || MRC=1
  done
  unset SMTPPASS RAW
  if [ $MRC -eq 0 ]; then log "📧 密码已发两处，销毁本地托管"; shred -u "$ESCROW/$BASE.pw" 2>/dev/null || rm -f "$ESCROW/$BASE.pw"; else log "⚠️ 邮件发送失败：密码保留在 $ESCROW/$BASE.pw"; alert "⚠️ 云端备份密码邮件发送失败，密码暂存于 $ESCROW/$BASE.pw（邮件恢复后再删）"; fi
fi
printf "{\"ts\":\"%s\",\"archive\":\"%s\",\"parts\":%s,\"sha256\":\"%s\",\"dst\":\"%s\",\"mail_ok\":%s}\n" "$(date -Iseconds)" "$BASE" "$PARTS" "$ENC_SHA" "$OUT" "$([ $MRC -eq 0 ] && echo true || echo false)" >> "$LED"
ls -1dt "$CLOUD"/*/ 2>/dev/null | tail -n +4 | xargs -r rm -rf
if ls "$CLOUD/$BASE"/*.baiduyun.uploading.cfg >/dev/null 2>&1; then log "⏳ 网盘客户端正在上传（正常）"; fi
log "🏁 完成：$OUT（$PARTS 片）"
exit 0