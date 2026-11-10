#!/bin/bash
# nas-move-98g-verify.sh —— 等搬运完成 → 校验大小 → 删本地副本（释放 D 盘）
W=/home/j/.openclaw/workspace
SRC=/mnt/d/WSL/ubuntu-20260929.tar
RF=/volume1/homes/jintianyu/果果回收站/ubuntu-20260929.tar
LOG=$W/state/nas-move-98g.log
# ⚠️ 2026-09-30 已完结：搬运成功并校验一致，本地副本已删。源路径已随 2026-10-22 盘位迁移失效。
#    没有守卫的话本脚本会空跑 240 分钟的等待循环（TOTAL=0 时永远等不到），故加守卫直接退出。
[ -f "$SRC" ] || { echo "已完结(2026-09-30)：本地副本已删、NAS 上已校验一致，本脚本留档不再重跑" >&2; exit 0; }
S="ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=15"
TOTAL=$(stat -c%s "$SRC" 2>/dev/null || echo 0)
RS=0
for i in $(seq 1 240); do
  sleep 60
  RS=$($S jintianyu@192.168.1.5 "stat -c%s '$RF' 2>/dev/null || echo 0" 2>/dev/null | tr -dc '0-9'); RS=${RS:-0}
  if [ "$RS" -ge "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then break; fi
done
if [ "$RS" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
  echo "$(date '+%F %T') ✅ 搬运完成并校验一致（$RS 字节）→ 删除本地副本，释放 D 盘" >> "$LOG"
  rm -f "$SRC"
  echo "OK total=$TOTAL" > "$W/state/nas-move-98g.done"
  echo "$(date '+%F %T') ✅ 本地已删，D 盘: $(df -h /mnt/d | tail -n1 | awk '{print $5" used"}')" >> "$LOG"
else
  echo "$(date '+%F %T') ⚠️ 超时或大小不一致（远端 $RS / 本地 $TOTAL），本地保留未删" >> "$LOG"
fi
