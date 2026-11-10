#!/bin/sh
# gateway-watch.sh —— 网关重启守望（2026-09-30 老板令「改」）
# 作用：检测网关是否被自动拉起 → 输出提示（由 5 分钟任务 announce 到飞书）
# 判据：ActiveEnterTimestamp 变化。若你没手动重启 → 就是系统自愈（Restart=always）✅
W=/home/j/.openclaw/workspace
F="$W/state/gateway-boot.last"
mkdir -p "$W/state"
cur=$(systemctl --user show openclaw-gateway -p ActiveEnterTimestamp --value 2>/dev/null)
if [ -z "$cur" ]; then echo "🔴 网关服务不在了！请检查（systemctl --user status openclaw-gateway）"; exit 0; fi
prev=$(cat "$F" 2>/dev/null)
if [ "$cur" != "$prev" ]; then
  printf '%s\n' "$cur" > "$F"
  # 主公令 2026-10-22 20:10：重启提示已合并进 notify-webaddr.sh 的单条消息，这里不再单独输出
  :
fi
