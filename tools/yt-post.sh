#!/bin/bash
# yt-post.sh —— 等批量下载结束 → 补 wav（用 ./ 前缀避免文件名以 - 开头被当参数）→ 清理分片 → 推飞书
set -u
U="${1:-oc-ytdl-run1}"
D=/home/j/openclaw-workspaces/print/inbox/yt
FFMPEG=/home/j/.local/bin/ffmpeg
for i in $(seq 1 200); do
  st=$(systemctl --user is-active "$U" 2>/dev/null)
  [ "$st" = "inactive" ] || [ "$st" = "failed" ] && break
  sleep 30
done
cd "$D" || exit 1
for v in ./*.mp4; do
  [ -s "$v" ] || continue
  case "$v" in *.f[0-9]*) continue;; esac
  w="${v%.mp4}.wav"
  [ -s "$w" ] || $FFMPEG -v error -y -i "$v" -vn -ac 1 -ar 16000 "$w" || echo "wav FAIL $v"
done
find . -maxdepth 1 -name '*.f1*.mp4' -size -2M -delete 2>/dev/null
find . -maxdepth 1 -name '*.part' -delete 2>/dev/null
cnt=$(ls -1 ./*.mp4 2>/dev/null | wc -l); wav=$(ls -1 ./*.wav 2>/dev/null | wc -l)
size=$(du -sh . 2>/dev/null | awk '{print $1}')
list=$(ls -1 ./*.mp4 2>/dev/null | xargs -r -n1 basename | head -12)
msg="YouTube 教学视频下载完成：mp4=$cnt wav=$wav 总大小=$size
$list
目录: $D"
echo "$msg" > /home/j/.openclaw/workspace/state/work/yt-download-report.txt
NOTIFY_ALERT=1 bash /home/j/.openclaw/workspace/tools/notify.sh "YouTube 教学视频下载完成｜$msg" >/dev/null 2>&1 || true
