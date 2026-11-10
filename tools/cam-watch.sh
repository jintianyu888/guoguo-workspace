#!/bin/bash
# cam-watch.sh <nvr通道号如101|302> —— 单路实时抓帧+人脸（供 systemd 常驻）
set -u
. /home/j/.config/hik-nvr.env
CH="${1:-101}"
URL="rtsp://admin:${HIK_NVR_PASS}@${HIK_NVR_IP:-192.168.1.103}:554/Streaming/Channels/${CH}"
exec /home/j/.openclaw/venvs/face/bin/python /home/j/.openclaw/workspace/tools/face-recognize.py watch \
  --url "$URL" --interval 2 --cooldown 60 --autolearn 1
