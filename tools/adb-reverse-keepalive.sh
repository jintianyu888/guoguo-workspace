#!/bin/bash
# 保持手机 USB 反向端口映射（短信接收通道）
ADB=/home/j/.local/opt/platform-tools/adb.exe
LOG=/home/j/.openclaw/workspace/state/sms/reverse.log
mkdir -p "$(dirname "$LOG")"
st=$("$ADB" devices 2>/dev/null | tr -d '\r' | awk 'NR==2{print $2}')
if [ "$st" != "device" ]; then
  echo "$(date -Is) skip dev=$st" >> "$LOG"
  exit 0
fi
cur=$("$ADB" reverse --list 2>/dev/null | grep -c 'tcp:18899 tcp:18899')
if [ "$cur" = "0" ]; then
  "$ADB" reverse tcp:18899 tcp:18899 >>"$LOG" 2>&1
  echo "$(date -Is) added" >> "$LOG"
else
  echo "$(date -Is) ok" >> "$LOG"
fi
tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
exit 0
