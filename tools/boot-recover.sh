#!/usr/bin/env bash
# 开机自愈（由 Windows 计划任务 OpenClaw-WSL-Boot 调用）
# 作用：等 systemd/用户实例就绪 → 确保网关启用并健康 → 检查关键挂载 → 落日志
# 只做启动与健康兜底；不触碰 cron、不删数据
set -u
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"
LOG=/home/j/.openclaw/workspace/state/log/boot-recover.log
mkdir -p "$(dirname "$LOG")"
say() { echo "[$(date '+%F %T')] $*" >>"$LOG"; }

say "=== boot-recover start (uptime $(cut -d' ' -f1 /proc/uptime)s) ==="

# 1) 等 systemd 用户实例
for i in $(seq 1 60); do
  st=$(systemctl --user is-system-running 2>/dev/null || true)
  case "$st" in running|degraded) say "user manager: $st"; break;; esac
  sleep 2
done

# 2) 确保网关服务启用并运行
systemctl --user enable --quiet openclaw-gateway.service 2>/dev/null || true
if ! systemctl --user is-active --quiet openclaw-gateway.service; then
  say "gateway 未运行 → start"
  systemctl --user start openclaw-gateway.service >>"$LOG" 2>&1 || say "start rc=$?"
fi

# 3) 健康探测（最多 3 分钟）
code=""
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:18789/health 2>/dev/null || true)
  [ "$code" = "200" ] && break
  sleep 2
done
say "gateway /health=$code"

# 4) 不健康才走受控重启脚本（带预告/冲突检查，懒加载）
if [ "$code" != "200" ]; then
  say "网关不健康 → tools/restart-gateway.sh --reason boot-recover"
  bash /home/j/.openclaw/workspace/tools/restart-gateway.sh --reason "boot-recover 开机自愈" >>"$LOG" 2>&1 || say "restart-gateway rc=$?"
  for i in $(seq 1 60); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:18789/health 2>/dev/null || true)
    [ "$code" = "200" ] && break
    sleep 2
  done
  say "重启后 /health=$code"
fi

# 5) 关键挂载检查（只记录，不自动修）
for m in /mnt/nas /mnt/e /mnt/x; do
  if mountpoint -q "$m"; then say "mount ok $m"; else say "mount MISSING $m"; fi
done

say "=== boot-recover done ==="
exit 0
