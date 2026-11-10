#!/bin/bash
# 人脸库取图（2026-11-07 主公令：只从监控提）：白天每 N 秒抓门口/大厅快照
# 频道：1501 门口左 / 1601 门口右 / 1001 大厅
set -uo pipefail
WS=/home/j/.openclaw/workspace
INV=${INV:-25}                      # 秒
OUT=$WS/state/faces/live
set -a; . ~/.config/hik-nvr.env; set +a
mkdir -p "$OUT"
log(){ echo "$(date '+%F %T') $*"; }
while :; do
  H=$(date +%H)
  if [ "$H" -lt 7 ] || [ "$H" -ge 21 ]; then sleep 300; continue; fi
  D=$(date +%Y%m%d)
  for ch in 1501 1601 1001; do
    dir=$OUT/$ch/$D; mkdir -p "$dir"
    f=$dir/$(date +%H%M%S).jpg
    code=$(curl -s --digest -u "$HIK_NVR_USER:$HIK_NVR_PASS" "http://$HIK_NVR_IP/ISAPI/Streaming/channels/${ch}/picture" --max-time 10 -o "$f" -w '%{http_code}' 2>/dev/null)
    if [ "$code" != "200" ] || [ ! -s "$f" ]; then rm -f "$f"; fi
  done
  # 控制总量：单频道每天最多 2000 张
  for ch in 1501 1601 1001; do
    dir=$OUT/$ch/$D; n=$(ls "$dir" 2>/dev/null | wc -l)
    if [ "$n" -gt 2000 ]; then ls -t "$dir" | tail -n +2001 | xargs -r -I{} rm -f "$dir/{}"; fi
  done
  sleep "$INV"
done
