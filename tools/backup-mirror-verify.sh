#!/bin/bash
# backup-mirror-verify.sh —— 备份镜像与校验（2026-11-22 重写）
# 设计：D→E 只镜像最新一份全量并按策略修剪；E→H 交后台单元单文件续传；不再整目录 rsync
# 根因：旧版每日 rsync 整个目录（D 5×126G / E 600G），9p 大文件写报 code 11 / Cannot allocate memory，
#       E 只进不出长期 91%+，H 全量长期 0 份。
set -u
. /home/j/.openclaw/workspace/tools/backup-wait-idle.sh
W=/home/j/.openclaw/workspace
LOG=$W/state/work/mirror-verify.log
LEDGER=$W/state/backup-mirror-ledger.jsonl
TS=$(date "+%F %T")
E_KEEP=${E_KEEP:-4}
ERRCNT=0
echo "==== $TS 镜像+校验 ====" >> "$LOG"

# ===== 1) D -> E：只镜像最新一份 =====
DNEW=$(ls -t /mnt/d/openclaw-backups/*openclaw-backup.tar.gz 2>/dev/null | head -1)
if [ -n "$DNEW" ] && [ -d /mnt/e/openclaw-backups ]; then
  BASE=$(basename "$DNEW")
  DS=$(stat -c %s "$DNEW" 2>/dev/null || echo 0)
  ES=$(stat -c %s "/mnt/e/openclaw-backups/$BASE" 2>/dev/null || echo 0)
  if [ "$DS" = "$ES" ] && [ "$DS" -gt 1000000000 ]; then
    echo "  d -> e : 最新一份已存在且大小一致（$((DS/1073741824))G），跳过拷贝" >> "$LOG"
    printf '{"ts":"%s","from":"d","to":"e","diffs":0,"mode":"size-only","rc":0,"status":"ok"}\n' "$TS" >> "$LEDGER"
  else
    CPOK=1
    for try in 1 2 3; do
      if rsync -a --partial --inplace "$DNEW" /mnt/e/openclaw-backups/ >> "$LOG" 2>&1; then CPOK=0; break; fi
      echo "  d -> e : 第 $try 次失败，30 秒后重试" >> "$LOG"; sleep 30
    done
    ES=$(stat -c %s "/mnt/e/openclaw-backups/$BASE" 2>/dev/null || echo 0)
    if [ "$CPOK" = "0" ] && [ "$DS" = "$ES" ]; then
      [ -f "$DNEW.sha256" ] && rsync -a --partial --inplace "$DNEW.sha256" /mnt/e/openclaw-backups/ >> "$LOG" 2>&1
      echo "  d -> e : 已镜像最新一份（$((DS/1073741824))G，大小一致）" >> "$LOG"
      printf '{"ts":"%s","from":"d","to":"e","diffs":0,"mode":"size-only","rc":0,"status":"ok"}\n' "$TS" >> "$LEDGER"
    else
      echo "  d -> e : 失败（D=$DS E=$ES cp_ok=$CPOK）" >> "$LOG"
      bash "$W/tools/notify.sh" "【备份镜像失败】d -> e 拷贝未通过（D=$DS E=$ES），详见 state/work/mirror-verify.log" >/dev/null 2>&1 || true
      ERRCNT=$((ERRCNT+1))
    fi
  fi
  # 修剪：E 只留最新 E_KEEP 份
  ls -t /mnt/e/openclaw-backups/*openclaw-backup.tar.gz 2>/dev/null | tail -n +$((E_KEEP+1)) | while read -r f; do
    rm -f "$f" "$f.sha256" 2>/dev/null && echo "  修剪 E：删除旧归档 $(basename "$f")" >> "$LOG"
  done
else
  echo "  d -> e : 源或目标不可见，跳过" >> "$LOG"
fi

# ===== 2) E -> H：交后台单元，只传最新一份（H 策略=每月 6 份） =====
ENEW=$(ls -t /mnt/e/openclaw-backups/*openclaw-backup.tar.gz 2>/dev/null | head -1)
if [ -n "$ENEW" ] && [ -d /mnt/h/openclaw-backups ]; then
  EBASE=$(basename "$ENEW")
  HS=$(stat -c %s "/mnt/h/openclaw-backups/$EBASE" 2>/dev/null || echo 0)
  ES2=$(stat -c %s "$ENEW" 2>/dev/null || echo 0)
  if [ "$HS" = "$ES2" ] && [ "$HS" -gt 1000000000 ]; then
    echo "  e -> h : 最新一份已在 H 且大小一致，跳过" >> "$LOG"
  elif systemd-run --user --collect --no-block --unit="mirror-e2h-$(date +%Y%m%d-%H%M)" \
      --description="E2H backup mirror" \
      nice -n 10 ionice -c2 -n7 rsync -a --partial --inplace --append-verify "$ENEW" /mnt/h/openclaw-backups/ >/dev/null 2>&1; then
    echo "  e -> h : 已交后台单元（只传 $EBASE）" >> "$LOG"
  else
    echo "  e -> h : 后台单元启动失败" >> "$LOG"
    bash "$W/tools/notify.sh" "【备份镜像】e-h 后台单元启动失败" >/dev/null 2>&1 || true
    ERRCNT=$((ERRCNT+1))
  fi
  # 修剪：H 上同名但大小不一致的文件＝断点残留，直接清掉（2026-11-22）
  for hf in /mnt/h/openclaw-backups/*openclaw-backup.tar.gz; do
    [ -f "$hf" ] || continue
    hb=$(basename "$hf")
    if [ -f "/mnt/e/openclaw-backups/$hb" ]; then
      hs=$(stat -c %s "$hf" 2>/dev/null || echo 0)
      es=$(stat -c %s "/mnt/e/openclaw-backups/$hb" 2>/dev/null || echo 0)
      if [ "$hs" != "$es" ]; then
        rm -f "$hf" && echo "  清理 H 断点残留：$hb（H=$hs E=$es）" >> "$LOG"
      fi
    fi
  done
  # 修剪：H 只留最新 H_KEEP 份
  H_KEEP=${H_KEEP:-6}
  ls -t /mnt/h/openclaw-backups/*openclaw-backup.tar.gz 2>/dev/null | tail -n +$((H_KEEP+1)) | while read -r f; do
    rm -f "$f" "$f.sha256" 2>/dev/null && echo "  修剪 H：删除旧归档 $(basename "$f")" >> "$LOG"
  done
else
  echo "  e -> h : 源或目标不可见，跳过" >> "$LOG"
fi

# ===== 3) 档案数对照 =====
for d in d e h; do
  echo "  $d 档案数: $(ls /mnt/$d/openclaw-backups/*openclaw-backup.tar.gz 2>/dev/null | wc -l)" >> "$LOG"
done

# ===== 4) 副本一致性抽检（若工具存在） =====
if [ -x "$W/tools/backup-copy-verify.py" ] && [ -f /mnt/d/openclaw-backups/*.tar.gz ]; then
  timeout 600 python3 "$W/tools/backup-copy-verify.py" >> "$W/state/work/copy-verify.out" 2>&1 || true
fi

if [ "$ERRCNT" -gt 0 ]; then
  echo "❌ 本轮有 $ERRCNT 处镜像失败，详见日志" >> "$LOG"
  exit 1
fi
echo "  本轮完成，无失败" >> "$LOG"
