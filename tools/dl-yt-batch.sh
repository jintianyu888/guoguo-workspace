#!/bin/bash
set -u
P=http://172.18.240.1:7891
D=/home/j/openclaw-workspaces/print/inbox/yt
mkdir -p "$D"; cd "$D" || exit 1
IDS="-vjCWgrc4-s _Pw6L1BRdoY jqMVs0fmU20 XN5F1WtfWk wfefyBk81OE SeJ6T_8iQ0Y 17TL2zSojK0 vFJXnive2qs"
for id in $IDS; do
  if [ -f "./$id.mp4" ] && [ -f "./$id.wav" ]; then echo "skip $id (done)"; continue; fi
  echo "=== $id start $(date +%T) ==="
  /home/j/.local/bin/yt-dlp --proxy "$P" --no-warnings --no-progress -i \
    --retries 10 --fragment-retries 10 --socket-timeout 20 \
    -f "bv*[height<=720]+ba/b[height<=720]/b" \
    --write-auto-sub --sub-langs "zh.*,en.*" --convert-subs vtt \
    --merge-output-format mp4 -o "%(id)s.%(ext)s" \
    "https://www.youtube.com/watch?v=$id" 2>&1 | grep -vE "^\[download\] +[0-9]" | tail -5
  ls -l "./$id".* 2>/dev/null | awk '{print $5, $NF}'
  if [ -f "./$id.mp4" ] && [ ! -f "./$id.wav" ]; then
    /home/j/.local/bin/ffmpeg -v error -y -i "./$id.mp4" -vn -ac 1 -ar 16000 "./$id.wav" && echo "wav ok $id"
  fi
  sleep 2
done
echo "=== ALL DONE $(date +%T) ==="
