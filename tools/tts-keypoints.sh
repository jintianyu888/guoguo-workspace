#!/bin/sh
# tts-keypoints.sh —— 把回复要点用本地 TTS 念出来（**零 token、不出内网**）
# 用法: tts-keypoints.sh <回复文本文件> [输出.ogg]
W=/home/j/.openclaw/workspace
IN="${1:?用法: tts-keypoints.sh <文本文件> [out.ogg]}"
OUT="${2:-/home/j/.openclaw/workspace/state/tmp/keypoints.ogg}"
KEY=$(python3 "$W/tools/tts-keypoints.py" "$IN" 2>/dev/null)
[ -n "$KEY" ] || { echo "无要点可念"; exit 0; }
echo "要念的：$KEY"
sh "$W/tools/tts.sh" "$KEY" "$OUT"