#!/usr/bin/env bash
# douyin-dl.sh —— 抖音专用下载包装（限速+真实UA+cookie），避免全局限速拖慢其它下载
# 用法: tools/douyin-dl.sh <url> [yt-dlp 其它参数...]
set -u
COOKIE="$HOME/.config/cooking-cookies/douyin.txt"
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
YTDLP="$HOME/.local/bin/yt-dlp"
[ -x "$YTDLP" ] || YTDLP="/home/j/.openclaw/workspace/state/dl/yt-dlp_nightly"
exec "$YTDLP" \
  --cookies "$COOKIE" \
  --user-agent "$UA" \
  --sleep-requests 2 --min-sleep-interval 3 --max-sleep-interval 8 \
  "$@"
