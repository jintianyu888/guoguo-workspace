#!/bin/bash
# 千问抢购窗口保活：检查 CDP 18811，不通则用同一 profile 重新拉起（登录态保留）
set -u
CDP=http://127.0.0.1:18811
URL="https://common-buy.aliyun.com/coding-plan"
CHROME=/home/j/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome
PROFILE=/home/j/.openclaw/browser-profiles/aliyun

if curl -s --max-time 5 "$CDP/json/version" | grep -q Chrome; then
  echo "OK 浏览器窗口在线"
  exit 0
fi
echo "浏览器不在，重新拉起..."
systemctl --user stop chromium-aliyun 2>/dev/null
systemd-run --user --unit=chromium-aliyun --collect \
  --setenv=DISPLAY=:0 --setenv=WAYLAND_DISPLAY=wayland-0 \
  --setenv=LD_LIBRARY_PATH=/home/j/.local/libs \
  "$CHROME" --remote-debugging-port=18811 --user-data-dir="$PROFILE" \
  --no-first-run --no-default-browser-check --disable-features=Translate "$URL" >/dev/null 2>&1
sleep 6
if curl -s --max-time 5 "$CDP/json/version" | grep -q Chrome; then
  echo "重新拉起成功"
else
  echo "拉起失败，需人工"
  /home/j/.openclaw/workspace/tools/notify.sh "⚠️千问抢购浏览器窗口拉起失败，明早需手动打开抢购页" >/dev/null 2>&1
  exit 1
fi
