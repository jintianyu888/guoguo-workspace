#!/bin/bash
# doctor-fix.sh —— 独立会话里跑的系统修复（2026-10-16 主公令：系统修复第一优先级）
# 必须从【网关进程树之外】运行（例如 Windows 端 wsl.exe 启动），否则 doctor 拒绝执行。
LOG=/home/j/.openclaw/workspace/state/doctor-fix.log
{
  echo "=== START $(date '+%F %T') ==="
  echo "[安全网] 4 分钟后无条件把网关拉起来"
  ( setsid nohup bash -c 'sleep 240; systemctl --user start openclaw-gateway' >/dev/null 2>&1 & ) 2>/dev/null || true
  echo "[1/4] 停止网关..."
  systemctl --user stop openclaw-gateway
  sleep 3
  echo "[2/4] 跑 openclaw doctor --fix ..."
  openclaw doctor --fix
  echo "doctor rc=$?"
  echo "[3/4] 启动网关..."
  systemctl --user start openclaw-gateway
  sleep 8
  echo "[4/4] 校验..."
  systemctl --user is-active openclaw-gateway
  systemctl --user show openclaw-gateway -p NRestarts -p MainPID | head -2
  echo "=== DONE $(date '+%F %T') ==="
} >> "$LOG" 2>&1
echo "日志: $LOG"
tail -30 "$LOG"
