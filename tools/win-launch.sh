#!/usr/bin/env bash
# win-launch.sh — 从 WSL 拉起 E:\openclaw-store\desktop-tools 下的 Windows 脚本（立即返回）
set -u
case "${1:-}" in
  compact)  BAT='E:\openclaw-store\desktop-tools\果果-压缩X盘-v2.bat' ;;
  sparse)   BAT='E:\openclaw-store\desktop-tools\Guoguo-enable-sparse.bat' ;;
  fstrim)   BAT='E:\openclaw-store\desktop-tools\果果-释放WSL空间.bat' ;;
  cfgcheck) BAT='E:\openclaw-store\desktop-tools\Guoguo-wslconfig-check.bat' ;;
  *) echo "未知目标: ${1:-}"; exit 2 ;;
esac
CMD=/mnt/c/Windows/System32/cmd.exe
[ -x "$CMD" ] || { echo "interop 不可用：找不到 cmd.exe"; exit 3; }
cd /mnt/c || exit 4
# 后台启动并切断所有句柄，否则 cmd 会挂住调用方
nohup "$CMD" /c start "" "$BAT" </dev/null >/dev/null 2>&1 &
rc=$?
if [ $rc -eq 0 ]; then echo "已交给 Windows 执行：$BAT"; else echo "启动失败 rc=$rc"; fi
exit $rc
