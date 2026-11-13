#!/usr/bin/env bash
# wb-start.sh —— 以调试端口重启 WorkBuddy（供 wb-ask.sh 使用），10 秒级，可回滚为普通启动
set -u
PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
if "$PS" -NoProfile -Command "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {\$_.LocalPort -eq 9222}" 2>/dev/null | grep -q 9222; then
  echo "WB_ALREADY_UP 9222 已就绪"; exit 0
fi
"$PS" -NoProfile -Command "Stop-Process -Name WorkBuddy -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 3" >/dev/null 2>&1
"$PS" -NoProfile -Command "Start-Process -FilePath 'D:\WorkBuddy\WorkBuddy.exe' -ArgumentList '--remote-debugging-port=9222'" >/dev/null 2>&1
sleep 15
if "$PS" -NoProfile -Command "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {\$_.LocalPort -eq 9222}" 2>/dev/null | grep -q 9222; then
  echo "WB_UP 9222 就绪"
else
  echo "WB_FAIL 9222 未起来"; exit 1
fi
