#!/bin/bash
# adb.sh v1.0 — WSL 侧调用 Windows 版 adb（USB 直连手机，不需要无线调试）
# 用法: bash tools/adb.sh devices | shell '<cmd>' | reverse-list | push/pull ...
set -uo pipefail
ADB=/home/j/.local/opt/platform-tools/adb.exe
[ -x "$ADB" ] || { echo 'adb.exe 不存在: '$ADB >&2; exit 3; }
cmd=${1:-devices}; shift || true
case "$cmd" in
  shell) cd /mnt/c && exec "$ADB" shell "$@" ;;
  devices|reverse-list|reverse|pull|push|install|uninstall|logcat) cd /mnt/c && exec "$ADB" "$cmd" "$@" ;;
  *) cd /mnt/c && exec "$ADB" "$cmd" "$@" ;;
esac