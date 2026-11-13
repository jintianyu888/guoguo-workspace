#!/usr/bin/env bash
# 等主公双击安装开机自启任务 → 自动验收并播报（一次性，最多 2 小时）
set -u
R=/mnt/c/openclaw/install-result.txt
BAT=/mnt/c/Users/J/Desktop/OpenClaw-开机自启-安装.bat
W=/home/j/.openclaw/workspace
for i in $(seq 1 120); do
  if [ -f "$R" ]; then
    if grep -q "RESULT=OK" "$R" 2>/dev/null; then
      # 立刻实跑一次验收（不重启机器也能验证脚本链路）
      /mnt/c/Windows/System32/schtasks.exe /run /tn "OpenClaw-WSL-Boot" >/dev/null 2>&1
      sleep 45
      OUT=$(/mnt/c/Windows/System32/schtasks.exe /query /tn "OpenClaw-WSL-Boot" /fo list /v 2>/dev/null | tr -d '\r' | grep -iE "状态|Status|上次结果|Last Result" | head -4)
      HEALTH=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:18789/health || true)
      PP=$(/mnt/c/Windows/System32/netsh.exe interface portproxy show v4tov4 2>/dev/null | tr -d '\r' | grep -E "18789|9443" | head -4)
      bash "$W/tools/notify.sh" "开机自启已装好（OpenClaw-WSL-Boot）
实跑一次：$OUT
网关 /health=$HEALTH
portproxy：$PP
以后重启 Windows 不用登录也会自动拉起 WSL 和网关。" "🟢 开机自启验收" 2>/dev/null || true
      echo "[$(date '+%F %T')] verified" >> "$W/state/log/boot-task-watch.log"
      exit 0
    else
      bash "$W/tools/notify.sh" "开机自启安装失败：$(cat "$R" | tr -d '\r' | head -5)" "🔴 开机自启失败" 2>/dev/null || true
      exit 1
    fi
  fi
  sleep 60
done
bash "$W/tools/notify.sh" "2 小时内没等到管理员安装（桌面上的 OpenClaw-开机自启-安装.bat 未执行），开机自启暂时没上。随时可双击重试；脚本已备好：C:\openclaw\boot-start.ps1（可回滚：删除计划任务 OpenClaw-WSL-Boot 即恢复原状）。" "🟡 开机自启待安装" 2>/dev/null || true
