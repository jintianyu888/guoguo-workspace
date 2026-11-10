#!/bin/bash
# x-vhdx-compact.sh —— X 盘 WSL 镜像瘦身（2026-11-02 起草，需主公批准后执行）
# 语义：0=成功  2=前置条件不满足（拒绝执行）  3=压缩失败  4=压缩后复核异常
# 说明：ext4.vhdx 只增不减，删数据不还盘；--set-sparse true 可回收未使用块。
set -uo pipefail
# ⚠️ 关键限制：本脚本一旦执行 `wsl --shutdown` 会把当前 WSL 一起关掉，
#    所以它不能从 WSL 内部跑。正确做法：在 Windows 侧运行 tools/x-vhdx-compact.bat。
if grep -qi microsoft /proc/version 2>/dev/null; then
  echo "⛔ 请在 Windows 侧运行 tools/x-vhdx-compact.bat（本脚本会关闭 WSL 自身，不能在里面跑）" >&2
  exit 2
fi

W=/home/j/.openclaw/workspace
LOG=$W/state/work/x-vhdx-compact.log
VHDX=/mnt/x/WSL/Ubuntu/ext4.vhdx
DISTRO=${WSL_DISTRO:-Ubuntu}
say(){ printf '%s %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG"; }

say "=== 前置检查 ==="
# 1) 今日全量归档存在且大小合理（> 10G），避免在备份没跑好时动磁盘
LATEST=$(ls -t /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then say "FAIL 今日全量归档不存在，拒绝执行"; exit 2; fi
SZ=$(stat -c %s "$LATEST" 2>/dev/null || echo 0)
if [ "$SZ" -lt 10000000000 ]; then say "FAIL 最新归档仅 $SZ 字节，疑似不完整，拒绝执行"; exit 2; fi
say "  最新归档 ok: $(basename "$LATEST") ($SZ)"

# 2) 避开 04:45 路由器断网窗（04:00-06:05）
H=$(date +%H)
if [ "$H" -ge 4 ] && [ "$H" -lt 6 ]; then say "FAIL 当前处于断网窗口(04:00-06:05)，拒绝执行"; exit 2; fi

# 3) 不在备份静默窗
if [ -f "$W/state/work/.backup-quiet" ]; then say "FAIL 备份静默窗生效中，拒绝执行"; exit 2; fi

# 4) 记录压缩前大小
BEFORE=$(/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile \
         -Command "(Get-Item 'X:\WSL\Ubuntu\ext4.vhdx').Length" 2>/dev/null | tr -d '\r\n')
[ -z "$BEFORE" ] && BEFORE=0
DF_BEFORE=$(df -h /mnt/x | awk 'NR==2{print $4}')
say "  压缩前: vhdx=$BEFORE 字节, X 可用=$DF_BEFORE"

say "=== 执行：停止设备侧活动 + 关闭 WSL ==="
touch "$W/state/work/.watchdog-pause" 2>/dev/null
/usr/bin/env wsl.exe --shutdown >>"$LOG" 2>&1 || true
sleep 5
/usr/bin/env wsl.exe --manage "$DISTRO" --set-sparse true >>"$LOG" 2>&1
RC=$?
if [ "$RC" != "0" ]; then
  say "FAIL --set-sparse 返回 rc=$RC（WSL 版本可能 < 2.0）"
  rm -f "$W/state/work/.watchdog-pause"
  exit 3
fi
say "  set-sparse true 完成"

say "=== 复核（重启后由网关守护自动拉起；此处等待 20s 再测）==="
sleep 20
AFTER=$(/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile \
        -Command "(Get-Item 'X:\WSL\Ubuntu\ext4.vhdx').Length" 2>/dev/null | tr -d '\r\n')
[ -z "$AFTER" ] && AFTER=0
DF_AFTER=$(df -h /mnt/x 2>/dev/null | awk 'NR==2{print $4}')
say "  压缩后: vhdx=$AFTER 字节, X 可用=$DF_AFTER"
rm -f "$W/state/work/.watchdog-pause"
if [ "$AFTER" -ge "$BEFORE" ] && [ "$BEFORE" != "0" ]; then
  say "WARN 未见缩小（稀疏盘按写入逐步回收，属正常，可隔日复查）"
fi
say "=== 完成。若异常：wsl --manage $DISTRO --set-sparse false 可回滚 ==="
sh "$W/tools/notify.sh" "X 盘 vhdx 压缩完成：$DF_BEFORE → $DF_AFTER 可用" >/dev/null 2>&1 || true
exit 0
