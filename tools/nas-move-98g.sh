#!/bin/bash
# nas-move-98g.sh —— 把 98G WSL 回滚包搬到群晖「回收站」（2026-09-30 老板令）
# 特性：断点续传（按已传字节 dd skip）、失败自动重试、全程写日志
WORK=/home/j/.openclaw/workspace
SRC=/mnt/d/WSL/ubuntu-20260929.tar
NAS=jintianyu@192.168.1.5
RDIR=/volume1/homes/jintianyu/果果回收站
RFILE="$RDIR/ubuntu-20260929.tar"
LOG=$WORK/state/nas-move-98g.log
# ⚠️ 2026-09-30 已完结：98G 回滚包已搬至 NAS（/volume1/homes/jintianyu/果果回收站/ubuntu-20260929.tar）并删除本地副本。
#    本脚本留档；源路径已随 2026-10-22 盘位迁移失效，重跑会直接退出。
[ -f "$SRC" ] || { echo "已完结(2026-09-30)：源文件已迁 NAS 并删除，本脚本留档不再重跑" >&2; exit 0; }
DONE=$WORK/state/nas-move-98g.done
SSH="ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=15"
TOTAL=$(stat -c%s "$SRC" 2>/dev/null) || { echo "$(date '+%F %T') 源文件不存在" >> "$LOG"; exit 1; }
$SSH "$NAS" "mkdir -p '$RDIR'" 2>/dev/null
echo "$(date '+%F %T') 开始搬迁：$SRC（$TOTAL 字节）→ $RFILE" >> "$LOG"
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  RS=$($SSH "$NAS" "stat -c%s '$RFILE' 2>/dev/null || echo 0" 2>/dev/null); RS=${RS:-0}
  case "$RS" in ''|*[!0-9]*) RS=0;; esac
  if [ "$RS" -ge "$TOTAL" ]; then
    echo "$(date '+%F %T') ✅ 完成（远端 $RS 字节）" >> "$LOG"
    echo "OK $RS" > "$DONE"; exit 0
  fi
  SKIP_MB=$(( RS / 1048576 ))
  echo "$(date '+%F %T') 第 ${attempt} 次尝试：远端已有 $RS 字节，从 ${SKIP_MB}MB 续传" >> "$LOG"
  dd if="$SRC" bs=1M skip="$SKIP_MB" 2>/dev/null | $SSH "$NAS" "cat >> '$RFILE'" 2>>"$LOG"
  sleep 3
done
echo "$(date '+%F %T') ❌ 10 次尝试后仍未完成" >> "$LOG"
exit 1
