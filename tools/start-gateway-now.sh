#!/bin/bash
# start-gateway-now.sh —— 面板之外的最后兜底：启动网关 + 看门狗定时器，清暂停标志
set -u
WS=/home/j/.openclaw/workspace
echo "== 启动 openclaw-gateway =="
systemctl --user start openclaw-gateway 2>&1 | tail -3
for i in $(seq 1 25); do
  H=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:18789/health 2>/dev/null)
  [ "$H" = "200" ] && break
  sleep 3
done
echo "健康=$H（等待 $((i*3)) 秒）"
echo "== 恢复看门狗定时器 =="
systemctl --user start oc-gateway-watchdog.timer 2>&1 | tail -2
echo "看门狗=$(systemctl --user is-active oc-gateway-watchdog.timer 2>/dev/null)"
rm -f "$WS/state/work/.watchdog-pause"
echo "已清除暂停标志"
[ "$H" = "200" ] && echo "✅ 网关已恢复" || echo "⚠️ 网关未就绪，看 journalctl --user -u openclaw-gateway"
