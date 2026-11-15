#!/bin/bash
# yt-lite.sh —— 生成手机流畅版（480p，~500kbps），供慢速外网直连观看
set -u
SRC=/home/j/.openclaw/workspace/state/share
D=/home/j/.openclaw/workspace/state/share/lite
FF=/home/j/.local/bin/ffmpeg
mkdir -p "$D"; cd "$SRC" || exit 1
for f in *.mp4; do
  case "$f" in lite/*) continue;; esac
  out="$D/$f"
  [ -s "$out" ] && { echo "skip $f"; continue; }
  echo "=== $f $(date +%T)"
  $FF -hide_banner -loglevel error -y -i "$f" \
    -vf "scale=-2:480" -c:v libx264 -preset veryfast -crf 30 -maxrate 700k -bufsize 1400k \
    -c:a aac -b:a 64k -movflags +faststart "$out" && echo "ok $f"
done
du -sh "$D"
