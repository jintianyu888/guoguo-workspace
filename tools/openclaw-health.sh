#!/bin/bash
# OpenClaw 健康自检 —— 全本地只读探针（不改配置/不迁移/不重启/不 kill）
set -uo pipefail
echo "🩺 OpenClaw 健康自检 · $(date +%Y-%m-%dT%H:%M)"
echo "【只读】不改配置 / 不迁移 / 不重启 / 不 kill"
GW=$(pgrep -af "dist/index.js gateway" | head -1)
if [ -n "$GW" ]; then echo "· 网关进程：✅ 运行中 (pid $(printf %s "$GW" | cut -d" " -f1))"; else echo "· 网关进程：❌ 未发现"; fi
P=$(ss -ltn 2>/dev/null | grep -c ":18789")
if [ "${P:-0}" -ge 1 ]; then echo "· 端口 18789：✅ 监听中"; else echo "· 端口 18789：❌ 未监听"; fi
echo "· 磁盘 /home：$(df -h /home | tail -1 | tr -s " " | cut -d" " -f4,5) （可用 / 已用%）"
echo "· 内存(MB 已用/可用)：$(free -m | sed -n 2p | tr -s " " | cut -d" " -f3,7)"
echo "· 负载 1/5/15m：$(cut -d" " -f1-3 /proc/loadavg)"
LOG=$(ls -t /tmp/openclaw/openclaw-*.log 2>/dev/null | head -1)
if [ -n "$LOG" ]; then echo "· 今日日志 ERROR/FATAL：$(grep -cE "] (ERROR|FATAL)" "$LOG" 2>/dev/null) 行"; else echo "· 日志：未找到"; fi
echo "· 定时任务总数：$(timeout 25 openclaw automations list --all 2>/dev/null | tail -n +2 | wc -l)"
# 2026-10-22：发行版已迁到 X 盘，加一行轻量盘位信息（不调 PowerShell，秒级）
VH=$(ls /mnt/*/WSL/*/ext4.vhdx 2>/dev/null | head -1)
if [ -n "$VH" ]; then
  echo "· WSL 盘位：$(echo "$VH" | cut -d/ -f3) 盘 · vhdx $(du -h "$VH" 2>/dev/null | cut -f1) · 根 fs $(df -h / | tail -1 | awk '{print $5}')"
else
  echo "· WSL 盘位：❌ 未找到 ext4.vhdx（跑 sh tools/wsl-disk-health.sh 查详情）"
fi
echo "· 定时任务调度器：$(timeout 20 openclaw automations status 2>/dev/null | head -2 | tr "\n" " ")"
echo "【说明】只读探测；发现问题仅报告，绝不自动修复（吸取上次教训）"
