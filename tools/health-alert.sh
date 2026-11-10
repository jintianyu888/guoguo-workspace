#!/usr/bin/env bash
# health-alert.sh v2 —— 备份/安全告警（说人话 + 去重 + 只报要紧的）
# v2 变更（2026-09-26 老板反馈"看不懂"）：
#   ① 不贴任务表格，改成人话
#   ② 只报【备份】【安全】类，心跳/发送类噪音单独归类且每天最多报 1 次
#   ③ 同一告警 6 小时内不重复（🔴 级除外）
W=/home/j/.openclaw/workspace; ST=$W/state/.alert-state
# 静默窗口：定时断网时段（默认 04:00–05:00）不报错（2026-10-05 主公令）
python3 "$W/tools/quiet_window.py" >/dev/null 2>&1 && exit 0
mkdir -p "$W/state" "$ST"; NOW=$(date +%s)
ALERTS=""; RED=0
add(){ ALERTS="${ALERTS}${ALERTS:+
}$1"; }
# ① 备份任务是否失败（只盯备份相关任务）
# 2026-10-24 修：原来 grep+awk 解析人读表格，把「备份管家闹钟」行的第 4 列(cron)
# 当成任务名 → 误报「备份任务失败：cron」。改走 --json 结构化解析（tools/backup-failed-jobs.py），
# 只认「启用中 + lastRunStatus=error」，停用的一次性任务不进告警。
# 2026-11-08 18:00 修（双审 kimi-k3.1-pro + zhipu/glm-5.3 一致）：同一份失败清单 6 小时内只报一次，
# 清单变化或恢复后再次失败立刻报；采集异常（非零退出）不视为恢复，保留去重状态。
BAD_RC=0
BAD=$(timeout 100 python3 "$W/tools/backup-failed-jobs.py" 2>/dev/null) || BAD_RC=$?
BAD=$(printf '%s\n' "$BAD" | LC_ALL=C sed '/^$/d' | LC_ALL=C sort)
if [ -n "$BAD" ]; then
  LASTF="$ST/backup-bad.last"; LASTT="$ST/backup-bad.ts"
  LASTS=$(cat "$LASTF" 2>/dev/null); LASTTS=$(cat "$LASTT" 2>/dev/null || echo 0)
  case "$LASTTS" in ''|*[!0-9]*) LASTTS=0;; esac
  if [ "$BAD" != "$LASTS" ] || [ $((NOW - LASTTS)) -ge 21600 ]; then
    add "🔴 备份任务失败：$BAD"; RED=1
    printf '%s' "$BAD" > "$LASTF"; echo "$NOW" > "$LASTT"
  fi
elif [ "$BAD_RC" -eq 0 ]; then
  rm -f "$ST/backup-bad.last" "$ST/backup-bad.ts"
fi
# ② 全量备份超期
# 2026-09-30: 全量归档落点已迁到 /mnt/d/openclaw-backups，取两处最新一份判定，避免旧落点造成的假告警
ARCH=$(ls -t /mnt/d/openclaw-backups/*.tar.gz /home/j/Backups/*.tar.gz 2>/dev/null | head -1)
if [ -n "$ARCH" ]; then
  AGE=$(( (NOW - $(stat -c %Y "$ARCH")) / 3600 ))
  [ "$AGE" -gt 30 ] && { add "🔴 最近一次完整备份已 ${AGE} 小时没更新（正常应 24 小时内）"; RED=1; }
else add "🔴 找不到任何完整备份！"; RED=1; fi
# ③ 磁盘（支持「暂停报警」：state/alert-snooze-disk-until 存 epoch，未过期则跳过）
SNZ=$W/state/alert-snooze-disk-until; SKIP_DISK=0
[ -f "$SNZ" ] && [ "$(cat "$SNZ" 2>/dev/null)" -gt "$NOW" ] 2>/dev/null && SKIP_DISK=1
if [ "$SKIP_DISK" = 0 ]; then
  U=$(df -h /home/j 2>/dev/null | awk 'NR==2{print $5}' | tr -d '%')
  [ -n "$U" ] && [ "$U" -gt 90 ] && { add "🔴 硬盘快满了（${U}%）"; RED=1; }
fi
# ④ 公网入口
if pgrep -x tailscaled >/dev/null 2>&1; then
  F=$(timeout 15 tailscale funnel status 2>/dev/null | grep -ciE 'https://')
  [ "${F:-0}" -gt 0 ] && { add "🔴 家里服务的公网入口意外开着（应为关闭）"; RED=1; }
fi
# ⑤ 工作区明文密钥
H=$(grep -rInE '(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,})' "$W" --include='*.md' --include='*.json' --include='*.sh' --exclude-dir=trajectory-exports --exclude-dir=.git 2>/dev/null | head -2)
[ -n "$H" ] && { add "🔴 工作区里疑似有明文密钥（位置已记录，请让我处理）"; RED=1; }
# ⑥ 其它任务异常（心跳/发送类）→ 每天最多报 1 次
OTHER=$(timeout 60 openclaw automations list --all 2>/dev/null | grep -iE 'error \(|failed' | grep -viE 'backup|备份' | head -2)
if [ -n "$OTHER" ]; then
  D=$ST/other-reported-$(date +%F)
  [ -f "$D" ] || { add "⚠️ 有自动任务在报错（非备份类，详见台账）"; touch "$D"; }
fi
# ⑦ WSL 盘位体检（2026-10-22 新增；只报失败级，警告级不刷屏）
if [ -f "$W/tools/wsl-disk-health.sh" ]; then
  timeout 240 sh "$W/tools/wsl-disk-health.sh" --quiet >/dev/null 2>&1
  RC=$?
  [ "$RC" = 2 ] && { add "🔴 WSL 盘位体检有失败项（盘位/发行版注册/vhdx/回滚镜像），详见 tools/wsl-disk-health.sh"; RED=1; }
fi
# 去重：普通 6 小时；🔴 2 小时（不刷屏）
HASH=$(printf "%s" "$ALERTS" | md5sum | cut -c1-12)
LD=$ST/last-hash; LT=$ST/last-time
WIN=21600; [ "$RED" = 1 ] && WIN=7200
if [ -n "$ALERTS" ]; then
  [ -f "$LD" ] && [ "$(cat "$LD")" = "$HASH" ] && [ -f "$LT" ] && [ $((NOW - $(cat "$LT"))) -lt $WIN ] && exit 0
fi
if [ -n "$ALERTS" ]; then
  echo "🚨【备份/安全提醒】$(date '+%m-%d %H:%M')"
  echo "$ALERTS"
  echo "—— 怎么办："
  echo "   · 我已开始处理能自动处理的"
  echo "   · 需要你定的：我会单独发一条，写清【建议怎么做 + 代价 + 你回哪句】"
  printf "%s" "$HASH" > "$LD"; printf "%s" "$NOW" > "$LT"
  echo "[$(date '+%F %T')] $ALERTS" >> "$W/state/security-alerts.md"
  MSG="🚨【备份/安全提醒】
$ALERTS"
  timeout 40 bash "$W/tools/notify.sh" --alert "$MSG" >/dev/null 2>&1 || true
fi

# ⑥ 磁盘水位硬闸（2026-11-07 #222 主公批准）：85% 清泄漏、92% 深度清理
bash "$W/tools/disk-watermark-guard.sh" >/dev/null 2>&1 || true
