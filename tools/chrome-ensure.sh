#!/usr/bin/env bash
# chrome-ensure.sh — 确保本机 Chromium(CDP 9333) 起着（无 sudo 依赖）
export LD_LIBRARY_PATH="$HOME/.local/chromelibs/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
export DISPLAY=:0
CH="$HOME/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
PROF=/home/j/.openclaw/workspace/state/chrome-prof2
if curl -s --max-time 4 http://127.0.0.1:9333/json/version >/dev/null 2>&1; then echo already-up; exit 0; fi
pkill -f 'remote-debugging-port=9333' 2>/dev/null
sleep 1
mkdir -p "$PROF"
setsid "$CH" --no-sandbox --disable-gpu --no-first-run --no-default-browser-check \
  --remote-debugging-port=9333 --user-data-dir="$PROF" about:blank \
  > /home/j/.openclaw/workspace/state/chrome.log 2>&1 < /dev/null &
sleep 9
curl -s --max-time 4 http://127.0.0.1:9333/json/version >/dev/null 2>&1 && echo up || echo FAIL
