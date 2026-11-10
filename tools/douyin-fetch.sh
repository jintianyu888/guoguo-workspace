#!/usr/bin/env bash
# douyin-fetch.sh <抖音链接或视频页URL> <输出.mp4>
# 真浏览器(非无头)+CDP 监听网络 → 截真实媒体流 → curl 下载 → ffmpeg 合成。
# 每次用【全新 profile + 干净重启】，避免抓到残留旧页面的流。
set -o pipefail
W=/home/j/.openclaw/workspace
export LD_LIBRARY_PATH="$HOME/.local/chromelibs/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
export DISPLAY=":0"
# 2026-10-15：chromium 崩溃后丢失，已重装（版本号会变），自动探测
CH=$(ls -d "$HOME"/.cache/ms-playwright/chromium-*/chrome-linux64/chrome 2>/dev/null | head -1)
[ -n "$CH" ] || CH="$HOME/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
COOKIE="$HOME/.config/cooking-cookies/douyin.txt"
URL="$1"; OUT="$2"
if [ -z "$URL" ] || [ -z "$OUT" ]; then echo "用法: douyin-fetch.sh <url> <out.mp4>"; exit 1; fi
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0 Safari/537.36'

# 1) 干净重启：杀掉旧的 9333 实例 + 全新 profile
pkill -f "remote-debugging-port=9333" 2>/dev/null
sleep 2
PROF=$(mktemp -d)
setsid "$CH" --no-sandbox --disable-gpu --no-first-run --no-default-browser-check \
  --remote-debugging-port=9333 --user-data-dir="$PROF" about:blank \
  > "$W/state/chrome.log" 2>&1 < /dev/null &
sleep 9
curl -s --max-time 4 http://127.0.0.1:9333/json/version >/dev/null 2>&1 || { echo "❌ Chromium/CDP 起不来"; exit 2; }

# 2) 注入 cookie
node "$W/tools/cdp.mjs" cookies "$COOKIE" >/dev/null 2>&1

# 3) 截流（先回 blank 清页面，再进目标）
node "$W/tools/cdp.mjs" goto about:blank 1500 >/dev/null 2>&1
TMP=$(mktemp)
node "$W/tools/cdp.mjs" capture "$URL" 24000 "$TMP" >/dev/null 2>&1
V=$(python3 -c "import json;h=json.load(open('$TMP'));v=[x for x in h if 'media-video' in x];print(v[-1] if v else '')")
A=$(python3 -c "import json;h=json.load(open('$TMP'));v=[x for x in h if 'media-audio' in x];print(v[-1] if v else '')")
if [ -z "$V" ]; then echo "❌ 没截到视频流（可能仍需登录/风控）"; rm -rf "$PROF"; exit 3; fi

# 4) 下载 + 合成
TV=$(mktemp --suffix=.mp4); TA=$(mktemp --suffix=.mp4)
curl -sL -A "$UA" -e 'https://www.douyin.com/' -o "$TV" "$V"
if [ -n "$A" ]; then curl -sL -A "$UA" -e 'https://www.douyin.com/' -o "$TA" "$A"; fi
mkdir -p "$(dirname "$OUT")"
if [ -s "$TA" ]; then ffmpeg -y -loglevel error -i "$TV" -i "$TA" -c copy "$OUT"; else cp "$TV" "$OUT"; fi
rm -f "$TV" "$TA" "$TMP"; rm -rf "$PROF"
echo "✅ 完成: $OUT ($(du -h "$OUT" | cut -f1))"
