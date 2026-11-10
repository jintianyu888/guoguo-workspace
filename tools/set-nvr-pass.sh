#!/bin/bash
# set-nvr-pass.sh — 交互式写入海康 NVR 凭据（密码不落 shell 历史、不进聊天）
# 用法: bash tools/set-nvr-pass.sh [--scan]
set -uo pipefail
ENVF="$HOME/.config/hik-nvr.env"
mkdir -p "$HOME/.config"; chmod 700 "$HOME/.config" 2>/dev/null || true
IP="${HIK_NVR_IP:-192.168.1.103}"
USERA="${HIK_NVR_USER:-admin}"
if [ -t 0 ]; then
  printf "海康 NVR 密码（输入不回显）: "
  IFS= read -rs PASS
  printf "\n"
else
  IFS= read -r PASS
fi
if [ -z "${PASS:-}" ]; then echo "未输入密码，中止"; exit 1; fi
umask 077
printf "HIK_NVR_IP=%s\nHIK_NVR_USER=%s\nHIK_NVR_PASS=%s\n" "$IP" "$USERA" "$PASS" > "$ENVF"
chmod 600 "$ENVF"
unset PASS
echo "已写入 $ENVF（权限 $(stat -c %a "$ENVF")）"
if [ "${1:-}" = "--scan" ]; then
  echo "--- 试跑人脸扫描 ---"
  cd "$HOME/.openclaw/workspace" && python3 tools/nvr-face-scan.py 2>&1 | tail -15
fi
