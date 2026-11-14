#!/usr/bin/env bash
# interop-watch.sh —— 每分钟探一次 WSL→Windows 互操作；恢复后自动接回摄像头守卫并通报
set -u
ST=/home/j/.openclaw/workspace/state/interop-watch
mkdir -p "$ST"
FLAG="$ST/recovered-at"
if /mnt/c/Windows/System32/cmd.exe /c "exit 0" >/dev/null 2>&1; then
  if [ ! -f "$FLAG" ]; then
    date -Iseconds > "$FLAG"
    systemctl --user enable --now oc-face-guard.service >/dev/null 2>&1
    bash /home/j/.openclaw/workspace/tools/notify.sh "【互操作已恢复】WSL→Windows 通道恢复，摄像头守卫已自动重新启用（oc-face-guard）。" >/dev/null 2>&1
    echo "$(date -Iseconds) recovered" >> "$ST/watch.log"
  fi
else
  rm -f "$FLAG" 2>/dev/null
  echo "$(date -Iseconds) still-broken" >> "$ST/watch.log"
fi
tail -200 "$ST/watch.log" > "$ST/watch.tmp" && mv "$ST/watch.tmp" "$ST/watch.log"
exit 0
