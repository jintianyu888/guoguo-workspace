#!/bin/bash
# 从门口/大厅摄像头抽帧用于建人脸库（2026-11-07）
# 用法: nvr-entrance-pull.sh <channel> <hour> [fps] [date]
set -uo pipefail
WS=/home/j/.openclaw/workspace
ch=${1:?channel}; hh=${2:?hour}; fps=${3:-0.2}; d=${4:-$(date +%F)}
out=$WS/state/faces/nvrframes/ch${ch}-h${hh}
echo "[$(date +%T)] ch=$ch hour=$hh fps=$fps date=$d -> $out"
python3 $WS/tools/nvr-fetch-isapi.py --channel "$ch" --date "$d" --hours "$hh" --fps "$fps" --out "$out"
echo "[$(date +%T)] done rc=$? files=$(find "$out" -name '*.jpg' 2>/dev/null | wc -l)"
