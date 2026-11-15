#!/bin/bash
# yt-batch.sh v2 —— 批量下 YouTube 教学视频（单文件 best mp4）+ 同名 wav
# v2：加间隔与退避，避免 YouTube 429；单文件格式免合并（无 JS runtime 环境更稳）
set -uo pipefail
OUT="${OUT:-/home/j/openclaw-workspaces/print/inbox/yt}"
PROXY="http://172.18.240.1:7891"
YTDLP=/home/j/.local/bin/yt-dlp
FFMPEG=/home/j/.local/bin/ffmpeg
mkdir -p "$OUT"; cd "$OUT" || exit 2
IDS="${*:-EfjXlQh-_cQ -vjCWgrc4-s _Pw6L1BRdoY jqMVs0fmU20 XN5F1WtfWk wfefyBk81OE SeJ6T_8iQ0Y 17TL2zSojK0 vFJXnive2qs}"
for id in $IDS; do
  echo "=== $id $(date '+%F %T') ==="
  if ls "$id"*.mp4 >/dev/null 2>&1 && [ -s "$(ls -t "$id"*.mp4 | head -1)" ]; then
    echo "skip: 已存在"
  else
    $YTDLP --proxy "$PROXY" --no-warnings --retries 3 --fragment-retries 5 \
      -f 'best[ext=mp4]/best' --no-part \
      -o '%(id)s - %(title).80s.%(ext)s' "https://youtu.be/$id" 2>&1 | tail -2
    sleep 45
  fi
  v=$(ls -t "$id"*.mp4 2>/dev/null | head -1)
  if [ -n "$v" ] && [ ! -f "${v%.mp4}.wav" ]; then
    $FFMPEG -y -loglevel error -i "$v" -vn -ac 1 -ar 16000 "${v%.mp4}.wav" && echo "wav ok"
  fi
done
echo "=== ALL DONE $(date '+%F %T') ==="
