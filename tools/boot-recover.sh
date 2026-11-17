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

# 6) 面板 / TLS 代理（只拉起，不改配置）
W=/home/j/.openclaw/workspace
for u in guoguo.service oc-panel.service oc-tlsproxy.service; do
  systemctl --user list-unit-files "$u" >/dev/null 2>&1 || continue
  if ! systemctl --user is-active --quiet "$u"; then
    say "$u 未运行 → start"
    systemctl --user start "$u" >>"$LOG" 2>&1 || say "$u start rc=$?"
  fi
done
PANEL=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:8899/ 2>/dev/null)
say "panel(8899) http=$PANEL"

# 7) portproxy 核对（Windows 侧由 openclaw-boot-heal.ps1 按新 IP 重写，这里只验结果）
PP=$(/mnt/c/Windows/System32/netsh.exe interface portproxy show v4tov4 2>/dev/null | tr -d '\r' | grep -E '18789|9443|8899' | tr -s ' ' | head -3)
say "portproxy: $(printf '%s' "$PP" | tr '\n' '|')"

# 7.5) 漏档补跑：把停机期间漏掉的轻活补上（备份/镜像/压缩/升级/外发一律不补）
UP=$(cut -d' ' -f1 /proc/uptime | cut -d. -f1)
SINCE=$(( UP / 60 + 5 ))
# 优先用「重启前打的标记」算真实停机时长（WSL uptime 只从 WSL 启动算，会漏掉停机那几小时）
MARK=/mnt/c/Users/J/openclaw-last-reboot.txt
if [ -f "$MARK" ]; then
  MT=$(tr -d '\r' < "$MARK" 2>/dev/null | head -1)
  MTS=$(date -d "$MT" +%s 2>/dev/null || echo 0)
  if [ "$MTS" -gt 0 ]; then
    D=$(( ($(date +%s) - MTS) / 60 + 5 ))
    if [ "$D" -gt 0 ] && [ "$D" -le 720 ]; then SINCE=$D; fi
  fi
fi
CARGS="--since-minutes $SINCE --max 6"
[ "${CATCHUP_DRY:-0}" = "1" ] && CARGS="$CARGS --dry-run"
say "漏档补跑 since-minutes=$SINCE"
timeout 900 python3 "$W/tools/cron-catchup.py" $CARGS >>"$LOG" 2>&1 || say "catchup rc=$?"

# 7.8) 一次性开机任务（state/work/post-boot.sh，执行后自动归档）
bash "$W/tools/post-boot-runner.sh" >>"$LOG" 2>&1 || say "post-boot-runner rc=$?"

# 8) 飞书报备（每次开机一条，别让人以为系统还没起来）
[ "${1:-}" = "--no-notify" ] || bash "$W/tools/notify.sh" "【开机自愈】WSL 已就绪：网关 /health=${code:-?}，面板 8899=${PANEL:-?}
挂载：$(for m in /mnt/nas /mnt/e /mnt/x; do mountpoint -q "$m" && printf '%s=ok ' "$m" || printf '%s=缺 ' "$m"; done)
portproxy：$(printf '%s' "$PP" | tr -s ' ' | tr '\n' ' ')" >/dev/null 2>&1 || say "notify rc=$?"

say "=== boot-recover done ==="
exit 0
