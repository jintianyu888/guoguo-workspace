#!/bin/sh
# tts-gpu.sh —— 本地 GPU 语音合成（Kokoro-82M；离线、零 token、走 CUDA，带 CPU 回退）
# 用法: tts-gpu.sh "文字" [out.wav|.ogg] [voice]
set -e
W=/home/j/.openclaw/workspace
VENV=/home/j/.openclaw/venvs/tts312
TXT="${1:?用法: tts-gpu.sh \"文字\" [out.wav|.ogg] [voice]}"
OUT="${2:-/home/j/.openclaw/workspace/state/tmp/tts-gpu.ogg}"
VOICE="${3:-zf_xiaoxiao}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
TMP=$(mktemp /home/j/.openclaw/workspace/state/tmp/tts-gpu-XXXX.wav)
"$VENV/bin/python" "$W/tools/tts_gpu.py" "$TXT" "$TMP" "$VOICE"
case "$OUT" in
  *.ogg) ffmpeg -y -loglevel error -i "$TMP" -c:a libopus -b:a 48k "$OUT" ;;
  *) cp "$TMP" "$OUT" ;;
esac
rm -f "$TMP"
echo "$OUT"
