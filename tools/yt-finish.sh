#!/bin/bash
# yt-finish.sh v1 —— 收尾：等下载结束 → 补无音轨视频 → 全量拷贝到 state/share → 推清单
set -u
SRC=/home/j/openclaw-workspaces/print/inbox/yt
DST=/home/j/.openclaw/workspace/state/share
YTDLP=/home/j/.local/bin/yt-dlp
FFMPEG=/home/j/.local/bin/ffmpeg
PROXY=http://172.18.240.1:7891
mkdir -p "$DST"; cd "$SRC" || exit 1
for i in $(seq 1 240); do
  a=$(systemctl --user is-active oc-ytdl-run1 2>/dev/null)
  { [ "$a" != "activating" ] && [ "$a" != "active" ]; } && break
  sleep 30
done
# 补无音轨的（video-only 下载）
for f in ./*.mp4; do
  case "$f" in *.f[0-9]*|*.temp.*) continue;; esac
  has=$($FFMPEG -hide_banner -i "$f" 2>&1 | grep -c 'Audio:')
  [ "$has" -eq 0 ] || continue
  id=$(basename "$f" .mp4)
  echo "noaudio: $id"
  $YTDLP --proxy "$PROXY" --no-warnings --no-progress --retries 4 \
    -f "bv*[height<=720]+ba/b[height<=720]" --merge-output-format mp4 \
    -o "./${id}.fix.%(ext)s" "https://www.youtube.com/watch?v=$id" 2>&1 | tail -2
  if [ -s "./${id}.fix.mp4" ]; then mv -f "./${id}.fix.mp4" "$f"; fi
done
for v in ./*.mp4; do
  case "$v" in *.f[0-9]*|*.temp.*) continue;; esac
  [ -s "$v" ] || continue
  w="${v%.mp4}.wav"; [ -s "$w" ] || $FFMPEG -v error -y -i "$v" -vn -ac 1 -ar 16000 "$w"
done
find . -maxdepth 1 \( -name '*.part' -o -name '*.temp.mp4' \) -delete 2>/dev/null
python3 /home/j/.openclaw/workspace/tools/yt-rename.py "$SRC" >/dev/null 2>&1 || true
for f in ./*.mp4 ./*.wav; do
  case "$f" in *.f[0-9]*|*.temp.*) continue;; esac
  [ -s "$f" ] && cp -f "$f" "$DST/"
done
n=$(ls -1 "$DST"/*.mp4 2>/dev/null | wc -l); w=$(ls -1 "$DST"/*.wav 2>/dev/null | wc -l)
sz=$(du -sh "$DST" | awk '{print $1}')
list=$(ls -1 "$DST"/*.mp4 | xargs -r -n1 basename)
msg="教学视频已就绪：mp4=$n wav=$w 合计=$sz
$list
手机下载: https://gy.taild2d30d.ts.net:8443/d0c4d4b3d6f1a1077bf8dce1/"
echo "$msg" > /home/j/.openclaw/workspace/state/work/yt-share-report.txt
NOTIFY_ALERT=1 bash /home/j/.openclaw/workspace/tools/notify.sh "$msg" >/dev/null 2>&1 || true
