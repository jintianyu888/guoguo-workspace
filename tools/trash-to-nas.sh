#!/bin/bash
# trash-to-nas.sh —— 本地回收站搬到群晖回收站（2026-09-30 老板令：回收统一放群晖）
W=/home/j/.openclaw/workspace
SRC=$W/回收站/items
# 2026-10-20 修：批次名按运行时日期生成（原写死 trash-20260930.tgz，
# 新批次会跟远端 23G 旧包比大小永远对不上，导致永远传不上去）
BATCH=trash-$(date +%Y%m%d-%H%M)
TGZ=$W/state/work/${BATCH}.tgz
NAS=nas
RDIR=/var/services/homes/guoguonas/trash/items
RTGZ="$RDIR/${BATCH}.tgz"
LOG=$W/state/trash-to-nas.log
S="ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=15"
echo "$(date '+%F %T') 开始打包本地回收站" >> "$LOG"
mkdir -p "$W/state/work"
tar czf "$TGZ" -C "$W/回收站" items 2>>"$LOG"
TS=$(stat -c%s "$TGZ" 2>/dev/null)
echo "$(date '+%F %T') 打包完成: $TS 字节" >> "$LOG"
$S "$NAS" "mkdir -p '$RDIR'" 2>/dev/null
for i in 1 2 3 4 5; do
  RS=$($S -n "$NAS" "stat -c%s '$RTGZ' 2>/dev/null || echo 0" 2>/dev/null | tr -dc '0-9'); RS=${RS:-0}
  [ "$RS" -ge "$TS" ] && break
  SKIP=$(( RS / 1048576 ))
  echo "$(date '+%F %T') 第 ${i} 次传输（远端 ${RS}，从 ${SKIP}MB 续）" >> "$LOG"
  # ⚠️ 这里【绝不能】加 -n：-n 会把管道数据丢弃 → 传过去 0 字节（2026-09-30 踩过）
  dd if="$TGZ" bs=1M skip="$SKIP" 2>/dev/null | $S "$NAS" "cat >> '$RTGZ'" 2>>"$LOG"
  sleep 3
done
RS=$($S -n "$NAS" "stat -c%s '$RTGZ' 2>/dev/null || echo 0" 2>/dev/null | tr -dc '0-9'); RS=${RS:-0}
if [ "${RS:-0}" = "$TS" ] && [ "$TS" -gt 0 ]; then
  echo "$(date '+%F %T') ✅ 已入库群晖（$RS 字节），本地 items 保留待你确认" >> "$LOG"
  echo "OK $RS" > "$W/state/trash-to-nas.done"
  rm -f "$TGZ"
else
  echo "$(date '+%F %T') ⚠️ 传输未完成（远端 $RS / 本地 $TS）" >> "$LOG"
fi
