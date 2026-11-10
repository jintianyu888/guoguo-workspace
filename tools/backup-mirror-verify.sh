#!/bin/bash
# backup-mirror-verify.sh —— 备份归档「镜像 D→E→H + 自动校验 + 写台账」
# 2026-10-02 主公令：镜像后必须自动校验（差异必须为 0），结果写台账
set -u
# 等空闲守卫（2026-10-02 主公令）：有其他备份/重活在跑就先等（flock 串行）
. /home/j/.openclaw/workspace/tools/backup-wait-idle.sh
W=/home/j/.openclaw/workspace
LOG=$W/state/work/mirror-verify.log
LEDGER=$W/state/backup-mirror-ledger.jsonl
TS=$(date '+%F %T')
echo "==== $TS 镜像+校验 ====" >> "$LOG"

ERRCNT=0
for pair in "d e" "e h"; do
  set -- $pair; SRC=/mnt/$1/openclaw-backups/; DST=/mnt/$2/openclaw-backups/
  [ -d "$SRC" ] || { echo "  跳过 $1->$2（源不存在）" >> "$LOG"; continue; }
  mkdir -p "$DST"
  rsync -a "$SRC" "$DST" >> "$LOG" 2>&1
  # 校验：周日强制全量 checksum，平日 size-only 快比对；单次上限 90 分钟，超时中止并告警
  if [ "$(date +%u)" = "7" ]; then MODE=checksum; CAP=21600; else MODE=size-only; CAP=5400; fi
  OUT=$(timeout "$CAP" rsync -n -ai --$MODE "$SRC" "$DST" 2>>"$LOG"); RC=$?
  N=$(printf '%s\n' "$OUT" | grep -c . )
  ST=ok
  if [ "$RC" != "0" ] && [ "$RC" != "124" ]; then
    case "$RC" in 23|24) ST=warn;; *) ST=error; ERRCNT=$((ERRCNT+1));; esac
    echo "  $1 -> $2 : rc=$RC（$ST），差异计数不可信，跳过判定；模式=$MODE" >> "$LOG"
    bash "$W/tools/notify.sh" "【备份校验异常】$1 -> $2 rc=$RC（$ST），模式 $MODE；详见 cloud 校验日志" >/dev/null 2>&1 || true
    printf '{"ts":"%s","from":"%s","to":"%s","diffs":%s,"mode":"%s","rc":%s,"status":"%s"}\n' "$TS" "$1" "$2" "$N" "$MODE" "$RC" "$ST" >> "$LEDGER"
    continue
  fi
  if [ "$RC" = "124" ]; then
    ST=timeout
    echo "  $1 -> $2 : 校验超时($CAP s)已中止，模式=$MODE" >> "$LOG"
    bash "$W/tools/notify.sh" "【备份校验超时】$1 -> $2 超过 $((CAP/60)) 分钟未完成（模式 $MODE），已中止；请检查 9p 挂载或拆分校验。" >/dev/null 2>&1 || true
  elif [ "$N" -gt 0 ]; then
    ST=diff
    echo "  $1 -> $2 : 差异 $N 条（模式 $MODE）" >> "$LOG"
    bash "$W/tools/notify.sh" "【备份不一致】$1 -> $2 差异 $N 条（模式 $MODE），请核对 ledger 清单。" >/dev/null 2>&1 || true
  else
    echo "  $1 -> $2 : 差异 0 条（模式 $MODE）" >> "$LOG"
  fi
  printf '{"ts":"%s","from":"%s","to":"%s","diffs":%s,"mode":"%s","rc":%s,"status":"%s"}\n' "$TS" "$1" "$2" "$N" "$MODE" "$RC" "$ST" >> "$LEDGER"
done

# 三地档案数对照
for d in d e h; do
  echo "  $d 档案数: $(ls /mnt/$d/openclaw-backups/*.tar.gz 2>/dev/null | wc -l)" >> "$LOG"
done
echo "==== 结束 ====" >> "$LOG"

# 2026-10-21 主公令：追加三处副本比对（D/E/H 同名+同大小+头尾抽样哈希）
if [ -f /home/j/.openclaw/workspace/tools/backup-copy-verify.py ]; then
  python3 /home/j/.openclaw/workspace/tools/backup-copy-verify.py >> /home/j/.openclaw/workspace/state/work/copy-verify.out 2>&1
  _cvrc=$?
  echo "copy-verify rc=$_cvrc" >> /home/j/.openclaw/workspace/state/work/copy-verify.out
fi

if [ "$ERRCNT" -gt 0 ]; then
  echo "❌ 本轮有 $ERRCNT 对镜像校验失败（rc 非 0/124），详见日志" >> "$LOG"
  exit 1
fi
