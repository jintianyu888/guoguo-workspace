#!/usr/bin/env bash
# boot-verify.sh —— WSL 每次启动后的自检（2026-11-21 立）
# 查：网关健康 / 面板 / Windows 互操作；有问题推飞书，正常只写日志
W=/home/j/.openclaw/workspace
LOG=$W/state/work/boot-verify.log
echo "=== $(date "+%F %T") boot-verify 开始 ===" >>"$LOG"

# 1) 等网关健康（最多 180 秒）
ok=0
for i in $(seq 1 60); do
  if curl -s -m 3 -o /dev/null -w "%{http_code}" http://127.0.0.1:18789/health 2>/dev/null | grep -q 200; then ok=1; break; fi
  sleep 3
done
GW=$([ $ok = 1 ] && echo OK || echo FAIL)

# 2) 面板
PANEL=$(curl -s -m 5 -o /dev/null -w "%{http_code}" http://127.0.0.1:8899/ 2>/dev/null)

# 3) Windows 互操作
if timeout 15 /mnt/c/Windows/System32/cmd.exe /c "echo x" >/dev/null 2>&1; then INTEROP=OK; else INTEROP=BROKEN; fi

echo "$(date "+%F %T") 网关=$GW 面板=$PANEL 互操作=$INTEROP" >>"$LOG"

# 4) 只在异常时推飞书
if [ "$GW" != "OK" ] || [ "$PANEL" != "200" ] || [ "$INTEROP" != "OK" ]; then
  msg="【开机自检】网关=$GW 面板=$PANEL 互操作=$INTEROP（时间 $(date "+%F %T")）"
  timeout 60 bash "$W/tools/notify.sh" "$msg" >/dev/null 2>&1 || true
  echo "$(date "+%F %T") 已推送告警" >>"$LOG"
fi
echo "=== $(date "+%F %T") boot-verify 结束 ===" >>"$LOG"