#!/bin/bash
# yt-2share.sh —— 等下载+后处理结束，把 mp4/wav 复制进 state/share 供手机下载，并推清单
set -u
SRC=/home/j/openclaw-workspaces/print/inbox/yt
DST=/home/j/.openclaw/workspace/state/share
mkdir -p "$DST"
for u in oc-ytdl-run1 oc-yt-post2; do
  for i in $(seq 1 240); do
    st=$(systemctl --user is-active "$u" 2>/dev/null)
    [ "$st" = "inactive" ] || [ "$st" = "failed" ] || [ -z "$st" ] && break
    sleep 30
  done
done
cd "$SRC" || exit 1
cnt=0
for f in ./*.mp4 ./*.wav; do
  [ -s "$f" ] || continue
  case "$f" in *.f1*) continue;; esac
  b=$(basename "$f")
  if [ ! -s "$DST/$b" ] || [ "$f" -nt "$DST/$b" ]; then cp -f "$f" "$DST/$b" && cnt=$((cnt+1)); fi
done
ls -1 "$DST"/*.mp4 > /tmp/share-list.txt 2>/dev/null
n=$(ls -1 "$DST"/*.mp4 2>/dev/null | wc -l); w=$(ls -1 "$DST"/*.wav 2>/dev/null | wc -l)
sz=$(du -sh "$DST" 2>/dev/null | awk '{print $1}')
list=$(ls -1 "$DST"/*.mp4 2>/dev/null | xargs -r -n1 basename | head -12)
msg="已放入手机可下载目录：mp4=$n wav=$w 合计=$sz（本次新拷 $cnt）
$list
地址: https://gy.taild2d30d.ts.net:8443/d0c4d4b3d6f1a1077bf8dce1/"
echo "$msg" > /home/j/.openclaw/workspace/state/work/yt-share-report.txt
NOTIFY_ALERT=1 bash /home/j/.openclaw/workspace/tools/notify.sh "$msg" >/dev/null 2>&1 || true
