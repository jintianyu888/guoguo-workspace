#!/bin/bash
P=http://172.18.240.1:7891
D=/home/j/openclaw-workspaces/print/inbox/yt
cd "$D" || exit 1
id=XN5F1-WtfWk
/home/j/.local/bin/yt-dlp --proxy "$P" --no-warnings --no-progress -i --retries 10 \
  -f "bv*[height<=720]+ba/b[height<=720]/b" \
  --write-auto-sub --sub-langs "zh.*,en.*" --convert-subs vtt \
  --merge-output-format mp4 -o "%(id)s.%(ext)s" \
  "https://www.youtube.com/watch?v=$id" 2>&1 | tail -3
[ -f "./$id.mp4" ] && /home/j/.local/bin/ffmpeg -v error -y -i "./$id.mp4" -vn -ac 1 -ar 16000 "./$id.wav" && echo "wav ok $id"
echo "=== EXTRA DONE $(date +%T) ==="
