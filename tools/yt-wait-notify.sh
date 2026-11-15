#!/bin/bash
# yt-wait-notify.sh —— 等 yt 批次结束，统计结果并推飞书（零 token）
set -u
U="${1:-oc-ytdl-run1}"
for i in $(seq 1 180); do
  st=$(systemctl --user is-active "$U" 2>/dev/null)
  [ "$st" = "inactive" ] || [ "$st" = "failed" ] && break
  sleep 30
done
D=/home/j/openclaw-workspaces/print/inbox/yt
cnt=$(ls -1 "$D"/*.mp4 2>/dev/null | wc -l)
size=$(du -sh "$D" 2>/dev/null | awk '{print $1}')
wav=$(ls -1 "$D"/*.wav 2>/dev/null | wc -l)
list=$(ls -1 "$D"/*.mp4 2>/dev/null | xargs -r -n1 basename | head -12)
msg="【YouTube 教学视频下载完成】mp4=$cnt wav=$wav 总大小=$size
$list
目录: $D"
echo "$msg" > /home/j/.openclaw/workspace/state/work/yt-download-report.txt
bash /home/j/.openclaw/workspace/tools/notify.sh "YouTube 下载完成" "$msg" 2>/dev/null || true
