#!/usr/bin/env bash
# notify-webaddr.sh —— 网关每次重启/恢复后，自动把控制面板网页地址发给主公
# 主公令 2026-10-20 19:17；幂等：网关 PID 不变则静默
set -uo pipefail
W=/home/j/.openclaw/workspace
ST=$W/state/work/webaddr.state

# 网关身份 = 18789 端口监听进程 PID（网关重启即变化）
GW_PID=$(ss -tlnp 2>/dev/null | grep ':18789' | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2)
[ -z "$GW_PID" ] && exit 0   # 网关不在线，等下轮

# 状态文件格式：PID|完整启动时间（2026-10-23 修：旧版按空格切列，上次启动只剩 "Fri"）
IFS='|' read -r LAST LAST_BOOT _ < "$ST" 2>/dev/null || true
BOOT=$(systemctl --user show openclaw-gateway -p ActiveEnterTimestamp --value 2>/dev/null)
[ "${LAST:-}" = "$GW_PID" ] && [ "${LAST_BOOT:-}" = "${BOOT:-}" ] && exit 0

WSL_IP=$(hostname -I | awk '{print $1}')
WIN_IP=$(timeout 12 /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {\$_.IPAddress -like '192.168.*'} | Select-Object -First 1).IPAddress" 2>/dev/null | tr -d '\r\n ')
PP=$(timeout 10 /mnt/c/Windows/System32/netsh.exe interface portproxy show all 2>/dev/null | grep -c 18789 || echo 0)

PP_DESC="未配置（手机打不开时回我一声，我去修）"
[ "${PP:-0}" -ge 1 ] 2>/dev/null && PP_DESC="已配置"
OCLAW_VER=$(timeout 15 openclaw --version 2>/dev/null | grep -oE '2026\.[0-9.]+' | head -1)

RESTART=""
if [ -n "${LAST_BOOT:-}" ] && [ -n "${BOOT:-}" ] && [ "$LAST_BOOT" != "$BOOT" ]; then
  mem=$(systemctl --user show openclaw-gateway -p MemoryCurrent --value 2>/dev/null)
  RESTART="🔄 网关重启过（自愈已生效，无需你手动救）
· 上次启动：$LAST_BOOT
· 本次启动：$BOOT
· 当前内存：$(( ${mem:-0}/1024/1024 ))MB（含缓存，跑大任务时会偏高）
"
fi
MSG="🤖 OpenClaw ${OCLAW_VER:-unknown} · 果果已恢复在线（PID $GW_PID）
${RESTART}本机浏览器：http://127.0.0.1:18789
手机/同WiFi设备：http://${WIN_IP:-未取到}:18789
（WSL 内部 $WSL_IP；Windows 端口转发：$PP_DESC）"

if bash "$W/tools/notify.sh" "$MSG"; then
  printf '%s|%s\n' "$GW_PID" "${BOOT:-unknown}" > "$ST"
fi
