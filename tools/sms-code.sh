#!/bin/bash
# sms-code.sh — 从已连接手机的「通知栏」读最新验证码（不再依赖 content://sms）
# 用法: sms-code.sh [关键词]  默认 拓竹|验证码
set -uo pipefail
ADB=/home/j/.local/opt/platform-tools/adb.exe
KEY="${1:-拓竹|验证码}"
OUT=$($ADB shell "dumpsys notification --noredact" 2>/dev/null | grep -E "android.text=String|tickerText=" | grep -E "$KEY" | head -6)
CODE=$(printf '%s\n' "$OUT" | grep -oE '[0-9]{6}' | head -1)
if [ -n "$CODE" ]; then
  SRC=$(printf '%s\n' "$OUT" | head -1 | cut -c1-90)
  printf 'CODE=%s\nSRC=%s\n' "$CODE" "$SRC"
  exit 0
fi
echo "NO_CODE"; exit 1
