#!/usr/bin/env bash
# face-daily.sh —— 每天把新采人脸过质量门、聚类，并与已建库比对，挑出新面孔候选
# 依赖：security 的 06:00 NVR 扫描先跑完
set -u
cd /home/j/.openclaw/workspace
source tools/face-env.sh
export FACE_GPU=1 FACE_DET_SIZE=320 OMP_NUM_THREADS=2
LOG=state/work/face-daily.log
{
  echo "=== $(date '+%F %T') face-daily 开始 ==="
  facepy tools/face-quality-index.py --det-size 320 --min-det 0.5 --min-size 55 --max-yaw 45 --max-pitch 40 --thr 0.55 --mincount 2 2>&1 | grep -aE '质量过滤|正脸聚类'
  OUT=$(facepy tools/face-unknown-groups.py 2>&1 | grep -avE 'FutureWarning|tform')
  echo "$OUT"
  N=$(echo "$OUT" | sed -n 's/^未知组 \([0-9][0-9]*\) 个.*/\1/p')
  DIR=$(echo "$OUT" | sed -n 's/^候选图目录: //p')
  echo "=== $(date '+%F %T') 结束，未知组 ${N:-0} ==="
  if [ "${N:-0}" -gt 0 ] 2>/dev/null; then
    timeout 60 bash tools/notify.sh "人脸库：采到 ${N} 组新面孔候选（库里没有的人），图在 ${DIR}，等主公认人" 2>&1 | tail -2
  fi
} >> "$LOG" 2>&1

# 留存策略：抓拍/候选图 7 天、采集原图 30 天（2026-11-07 主公批准）
timeout 120 bash /home/j/.openclaw/workspace/tools/face-retention.sh || true
