#!/bin/bash
# cam.sh — 得力 4K 摄像头（Deli-4K-Camera）抓帧/录音/连拍
# 用法: cam.sh shot [输出路径]   |   cam.sh mic [秒数] [输出路径]   |   cam.sh info
# 依赖: C:\Windows\Temp\oc-tools\ffmpeg.exe（2026-11-14 装，免管理员）
set -uo pipefail
FF="/mnt/c/Users/J/AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe"  # winget Gyan.FFmpeg 9.0.2
VID="Deli-4K-Camera"
MIC="@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\\wave_{53D1932E-80F8-47C2-B5BF-04259FABB851}"
OUTDIR=/home/j/.openclaw/workspace/state/cam
mkdir -p "$OUTDIR"
case "${1:-info}" in
  shot)
    out="${2:-$OUTDIR/shot-$(date +%Y%m%d-%H%M%S).jpg}"
    "$FF" -hide_banner -loglevel error -f dshow -rtbufsize 100M -i "video=$VID" -frames:v 1 -y "$out" || exit 2
    echo "$out";;
  mic)
    sec="${2:-5}"; out="${3:-$OUTDIR/mic-$(date +%Y%m%d-%H%M%S).wav}"
    "$FF" -hide_banner -loglevel error -f dshow -i "audio=$MIC" -t "$sec" -ac 1 -ar 16000 -y "$out" || exit 3
    ffmpeg -hide_banner -i "$out" -af volumedetect -f null /dev/null 2>&1 | grep -E "mean_volume|max_volume"
    echo "$out";;
  info)
    "$FF" -hide_banner -list_devices true -f dshow -i dummy 2>&1 | sed -n '1,12p';;
  *) echo "usage: cam.sh shot [out] | mic [sec] [out] | info"; exit 1;;
esac
