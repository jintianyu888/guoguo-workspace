#!/usr/bin/env bash
# gateway-probe.sh v1 (2026-10-31) — Windows 侧探活的 WSL 端实现（UTF-8 中文不再乱码）
set -uo pipefail
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
W=/home/j/.openclaw/workspace
probe(){ curl -s -o /dev/null -w '%{http_code}' -m 10 http://127.0.0.1:18789/ 2>/dev/null; }

# 2026-11-01 保活自愈：保活进程不在时先补一个，避免本探针成为"最后一个会话"触发整机关机
if ! pgrep -fx "/bin/sh -c while true; do sleep 3600; done" >/dev/null 2>&1; then
  /mnt/c/Windows/System32/schtasks.exe /Run /TN WSL-KeepAlive >/dev/null 2>&1 || true
fi

for i in 1 2 3; do
  [ "$(probe)" = "200" ] && exit 0
  sleep 10
done

systemctl --user start openclaw-gateway >/dev/null 2>&1 || true
for i in $(seq 1 6); do
  sleep 10
  if [ "$(probe)" = "200" ]; then
    timeout 60 bash "$W/tools/notify.sh" "【探活自愈】网关曾连续 3 次无响应，已自动拉起并恢复" >/dev/null 2>&1
    exit 0
  fi
done

timeout 60 bash "$W/tools/notify.sh" --alert "【探活告警】网关连续 3 次探测无响应，自动拉起后仍未恢复，需人工介入" >/dev/null 2>&1
exit 0
