#!/bin/bash
set -u
SRC=/home/j/openclaw-workspaces/print/inbox/yt
DST="/mnt/c/Users/J/Desktop/叹息教程/YouTube教学"
mkdir -p "$DST"
cd "$SRC" || exit 1
for f in ./*.mp4 ./*.wav ./*.vtt 清单-YouTube素材.txt; do
  [ -f "$f" ] || continue
  cp -f "$f" "$DST/"
done
echo "=== 复制完成 $(date +%T) ==="
ls -1 "$DST" | wc -l
du -sh "$DST"
