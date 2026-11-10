#!/bin/bash
# migrate-old-nas.sh —— 老 NAS OpenClaw 归档迁到新 NAS（只迁我们自己的备份目录）
# 边界：/volume1/金鱼 下的个人数据一律不碰；只迁 homes/jintianyu/openclaw-archives
set -uo pipefail
SRC="jintianyu@192.168.1.5:/volume1/homes/jintianyu/openclaw-archives/"
DST="/mnt/nas/archive/jinyu/openclaw-archives/"
LOG=/home/j/.openclaw/workspace/state/migrate-old-nas.log
RES=/home/j/.openclaw/workspace/state/migrate-old-nas.result
SSHOPT="-o ConnectTimeout=10 -o BatchMode=yes"
log(){ printf "%s %s\n" "$(date "+%F %T")" "$*" | tee -a "$LOG"; }
mkdir -p "$DST"
# 等 H 盘归档跑完，避免抢带宽
while systemctl --user is-active nas-archive-legacy.service >/dev/null 2>&1; do sleep 60; done
log "START 老 NAS 归档迁移"
mountpoint -q /mnt/nas || { log "FAIL /mnt/nas 未挂载，中止"; echo "RESULT=NO_MOUNT" > "$RES"; exit 1; }
for try in 1 2 3; do
  log "COPY 第${try}次 rsync"
  if rsync -a --partial --append-verify -e "ssh $SSHOPT" "$SRC" "$DST" >> "$LOG" 2>&1; then
    log "COPY 完成"; break
  fi
  log "COPY 失败，60s 后重试"; sleep 60
done
# 数量与大小核对
SRC_N=$(ssh $SSHOPT synology-nas "ls -1 /volume1/homes/jintianyu/openclaw-archives/*.tar.gz 2>/dev/null | wc -l" 2>/dev/null | tr -d " ")
DST_N=$(ls -1 "$DST"*.tar.gz 2>/dev/null | wc -l | tr -d " ")
log "数量核对 源=$SRC_N 目标=$DST_N"
FAIL=0
[ "$SRC_N" = "$DST_N" ] || { log "FAIL 数量不符"; FAIL=1; }
# 逐文件哈希核对
ssh $SSHOPT synology-nas "cd /volume1/homes/jintianyu/openclaw-archives && sha256sum *.tar.gz" 2>/dev/null > /tmp/old-nas-hashes.txt
while read -r h f; do
  [ -z "$h" ] && continue
  lh=$(sha256sum "$DST$f" 2>/dev/null | cut -d" " -f1)
  if [ "$h" = "$lh" ]; then log "OK $f"; else log "FAIL $f 源=$h 目标=$lh"; FAIL=1; fi
done < /tmp/old-nas-hashes.txt
if [ "$FAIL" = 0 ]; then echo "RESULT=ALL_OK" > "$RES"; log "DONE 全部校验通过"; else echo "RESULT=FAIL" > "$RES"; log "DONE 有失败项，老 NAS 暂不可退役"; fi
