#!/bin/bash
# 高效版：3 路并行 × (7:00-23:00) × 0.05fps × 跳过 04 点
cd /home/j/.openclaw/workspace
D=${1:-$(date +%F)}
PY=/home/j/.openclaw/venvs/face/bin/python
for grp in "101,301,701" "1001,1201,1301" "1401,1501,1601"; do
  $PY tools/nvr-face-scan.py --date "$D" --channels $grp --hours 7-23 --skip-hours 4 --fps 0.05 &
done
wait
echo "🎬 NVR人脸扫描($D)完成 · 库共 $(ls state/faces/collected 2>/dev/null | wc -l) 张"
