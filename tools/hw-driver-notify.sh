#!/bin/bash
# hw-driver-notify.sh —— 驱动升级提示（2026-10-21 主公令）
# 逻辑：重跑硬件体检 → 读 win-driver-report.txt → 与上次指纹比对 → 变了且有建议才推飞书
W=/home/j/.openclaw/workspace
REPORT=/mnt/c/Users/Public/win-driver-report.txt
PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
LAST=$W/state/hw-driver.last
mkdir -p "$W/state"

# 1) 重新体检（只读；失败则用上一次的报告，不阻断）
"$PS" -NoProfile -ExecutionPolicy Bypass -File 'C:\\Users\\Public\\win-hw.ps1' >/dev/null 2>&1
[ -s "$REPORT" ] || { echo "无驱动报告，跳过"; exit 0; }

# 2) 指纹（去掉首行时间戳，避免每天都说“变了”）
BODY=$(tail -n +2 "$REPORT" | tr -d '\r')
FP=$(printf '%s' "$BODY" | sha256sum | cut -d' ' -f1)

# 3) 首次运行只记指纹，不推送（避免重复报老问题）
if [ ! -f "$LAST" ]; then
  printf '%s' "$FP" > "$LAST"
  echo "首次运行，已记录指纹，不推送"
  exit 0
fi

OLD=$(cat "$LAST" 2>/dev/null)
[ "$FP" = "$OLD" ] && { echo "驱动状态无变化"; exit 0; }
printf '%s' "$FP" > "$LAST"

# 4) 只在“有升级建议”时推送
if printf '%s' "$BODY" | grep -q '无需升级'; then echo "无待升级驱动"; exit 0; fi
MSG=$(printf '🔧 驱动升级提示（%s）\n\n%s\n\n可选动作：装厂商最新驱动；不确定要不要升就问我。' "$(date +%m-%d)" "$BODY")
bash "$W/tools/notify.sh" "$MSG" >/dev/null 2>&1
echo "已推送驱动升级提示"
