#!/bin/bash
# 果果助手 WSL 侧命令分发器  v4.0.0  (2026-10-29 重写：修 10.8 解析失效 + 一键自检/升级)
set -u -o pipefail
export PATH=/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
WS=/home/j/.openclaw/workspace
cd "$WS" || exit 3
CMD="${1:-}"; shift || true
LOG=$WS/state/desktop-console/actions.log
mkdir -p "$(dirname "$LOG")" "$WS/state/diag"
say(){ printf '%s\n' "$*"; }
audit(){ printf '%s|%s|%s\n' "$(date '+%F %T')" "$CMD" "$*" >> "$LOG"; }
hr(){ say "----------------------------------------------"; }

gw_health(){ timeout 6 curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/health 2>/dev/null || echo 000; }
gw_pid(){ timeout 3 systemctl --user show -p MainPID --value openclaw-gateway 2>/dev/null | tr -d '\r'; }
gw_rss(){ local p; p=$(gw_pid); [ -n "$p" ] && [ "$p" != "0" ] && awk '/VmRSS/{printf "%.1f", $2/1048576}' /proc/$p/status 2>/dev/null || echo 0; }
ver(){ timeout 20 openclaw --version 2>/dev/null | head -1 || echo "未知"; }
cron_count(){ local o; o=$(timeout 25 openclaw cron list --json 2>/dev/null | python3 -c "import json,sys
try:
    d=json.load(sys.stdin); j=d if isinstance(d,list) else d.get('jobs',d.get('data',[]))
    print(len(j), sum(1 for x in j if x.get('enabled')))
except Exception: print('0 0')" 2>/dev/null); echo "${o:-0 0}" | head -1; }
backup_age(){ local f; f=$(ls -t /mnt/d/openclaw-backups/*openclaw-backup.tar.gz 2>/dev/null | head -1); [ -z "$f" ] && { echo "无归档"; return; }
  local m; m=$(stat -c %Y "$f" 2>/dev/null); echo "$(( ( $(date +%s) - m ) / 3600 )) 小时前 ($(stat -c %s "$f" 2>/dev/null | awk '{printf "%.1fG", $1/1073741824}'))"; }

case "$CMD" in
status)
  H=$(gw_health); P=$(gw_pid); V=$(ver)
  say "网关 health : $H"
  if [ "$H" = "200" ]; then C=$(cron_count); else C="跳过"; fi
  say "进程 PID    : $P"
  say "运行时长    : $(timeout 5 systemctl --user show -p ActiveEnterTimestamp --value openclaw-gateway 2>/dev/null | tr -d '\r')"
  say "内存占用    : $(gw_rss) GB / 上限 $(timeout 5 systemctl --user show -p MemoryMax --value openclaw-gateway 2>/dev/null | awk '{printf "%.0fG", $1/1073741824}')"
  say "软件版本    : $V"
  if [ "$C" = "跳过" ]; then say "定时任务    : 跳过（网关未响应，点[2]修复或[4]重启）"; else say "定时任务    : $(echo "$C" | cut -d' ' -f1) 个（启用 $(echo "$C" | cut -d' ' -f2)）"; fi
  say "看门狗      : $(systemctl --user is-active oc-gateway-watchdog.timer 2>/dev/null)"
  say "负载(1/5/15): $(cut -d' ' -f1-3 /proc/loadavg)"
  say "内存        : 已用 $(free -m | awk '/Mem:/{printf "%.1fG/%.1fG", $3/1024, $2/1024}')"
  say "根盘已用    : $(df -P / | tail -1 | tr -s ' ' | cut -d' ' -f5)"
  say "最近备份    : $(backup_age)"
  audit "h=$H pid=$P"
  ;;
selfcheck)
  say "===== 一键自检 $(date '+%F %T') ====="
  P=0; W=0; F=0
  chk(){ if [ "$2" = "pass" ]; then say "✅ $1"; P=$((P+1)); elif [ "$2" = "warn" ]; then say "⚠️  $1"; W=$((W+1)); else say "❌ $1"; F=$((F+1)); fi; }
  [ "$(systemctl --user is-active openclaw-gateway 2>/dev/null)" = "active" ] && chk "网关服务 active" pass || chk "网关服务 未运行" fail
  H=$(gw_health); [ "$H" = "200" ] && chk "健康端点 200" pass || chk "健康端点 $H" fail
  R=$(gw_rss); MX=$(timeout 5 systemctl --user show -p MemoryMax --value openclaw-gateway 2>/dev/null)
  LIM=$(awk -v m="$MX" 'BEGIN{printf "%.0f", m/1073741824}')
  if [ "$(echo "$R < $LIM * 0.7" | bc 2>/dev/null || echo 1)" = "1" ]; then chk "内存 $R G / 上限 $LIM G" pass; else chk "内存 $R G / 上限 $LIM G 偏高" warn; fi
  [ "$(systemctl --user is-active oc-gateway-watchdog.timer 2>/dev/null)" = "active" ] && chk "看门狗定时器 运行中" pass || chk "看门狗定时器 未运行" warn
  if [ "$H" = "200" ]; then
    C=$(cron_count); N=$(echo "$C" | cut -d' ' -f1); E=$(echo "$C" | cut -d' ' -f2)
    [ "$N" -gt 50 ] 2>/dev/null && chk "定时任务 $E/$N 启用" pass || chk "定时任务异常 ($C)" fail
  else chk "网关未响应，任务数跳过" fail; fi
  OOM=$(journalctl -k --since "-24h" --no-pager 2>/dev/null | grep -ci "oom-kill" || true); OOM=${OOM:-0}
  [ "$OOM" = "0" ] && chk "24h 内核 OOM 0 次" pass || chk "24h OOM $OOM 次" warn
  BA=$(backup_age); case "$BA" in *小时前*) HH=$(echo "$BA" | cut -d' ' -f1); [ "$HH" -lt 30 ] 2>/dev/null && chk "最近备份 $BA" pass || chk "最近备份 $BA 偏旧" warn;; *) chk "备份 $BA" warn;; esac
  for d in / /mnt/e /mnt/h /mnt/d /mnt/x; do
    u=$(df -P "$d" 2>/dev/null | tail -1 | tr -s ' ' | cut -d' ' -f5 | tr -d '%')
    [ -z "$u" ] && continue
    [ "$u" -ge 90 ] && chk "磁盘 $d 已用 $u%" warn || chk "磁盘 $d 已用 $u%" pass
  done
  SW=$(free -m | awk '/Swap:/{printf "%d", $3*100/$2}'); [ "$SW" -lt 50 ] && chk "Swap 使用 $SW%" pass || chk "Swap 使用 $SW% 偏高" warn
  hr; say "结论：PASS $P / WARN $W / FAIL $F"
  [ "$F" -gt 0 ] && say "建议：有 FAIL 项，点「一键修复」或「一键自救」"
  audit "P=$P W=$W F=$F"
  ;;
upgrade)
  say "===== 一键升级 ====="
  CUR=$(ver); say "当前版本：$CUR"
  say "将依次执行：预检 → 备份（配置+4 个数据库快照）→ 安装 → 重启 → 验证 → 自检对齐 → 报告"
  say "预计 5–10 分钟，其间网关中断约 60–120 秒；失败自动回滚，不会留在半残状态"
  if [ -t 0 ]; then
    printf "确认升级请输入 yes："; read -r ans
    [ "$ans" = "yes" ] || { say "已取消"; exit 0; }
  else
    say "（非交互调用：面板已二次确认，直接执行）"
  fi
  UARGS=""
  [ "${UPGRADE_DRYRUN:-0}" = "1" ] && { UARGS="--dry-run"; say "（演练模式：只做预检+备份，不安装）"; }
  say "→ 执行 tools/upgrade-panel.sh（npm 直装 + 快照 + 自动回滚，实时输出）..."
  bash "$WS/tools/upgrade-panel.sh" $UARGS 2>&1 | tee -a "$WS/state/work/upgrade-console.log"
  RC=${PIPESTATUS[0]}
  say "→ rc=$RC；成功=「✅ 升级完成」+版本号，失败=「↩️ 已回滚」；全过程日志 state/work/upgrade-panel.log，快照目录 state/backup/upgrade-snap-*"
  audit "upgrade rc=$RC dry=${UPGRADE_DRYRUN:-0}"
  ;;
restart)
  say "正在走受控重启（含预告/健康校验）..."
  bash tools/restart-gateway.sh --reason "果果助手手动重启" 2>&1 | tail -8
  audit "restart"
  ;;
fix)
  say "===== 一键自检 + 自动修复 ====="
  exec bash "$WS/tools/autofix.sh"
  audit "autofix"
  return 0 2>/dev/null || exit 0
  ;;
fix_legacy)
  say "===== 一键修复 ====="
  say "→ 检查配置可解析"
  if python3 -c "import json;json.load(open('/home/j/.openclaw/openclaw.json'))" 2>/dev/null; then say "  配置 OK"; else say "  配置损坏！从最近备份恢复"; ls -t /home/j/.openclaw/openclaw.json.bak-* 2>/dev/null | head -1 | xargs -r cp -f /home/j/.openclaw/openclaw.json; fi
  say "→ 重启看门狗"
  systemctl --user reset-failed oc-gateway-watchdog.service 2>/dev/null; systemctl --user restart oc-gateway-watchdog.timer 2>&1 | tail -2
  say "→ 网关状态：$(systemctl --user is-active openclaw-gateway 2>/dev/null)"
  if [ "$(gw_health)" != "200" ]; then say "→ 健康异常，走受控重启"; bash tools/restart-gateway.sh --reason "一键修复：健康异常" 2>&1 | tail -6; fi
  say "→ 清理陈旧锁"
  rm -f "$WS"/state/work/.safe-restart-running 2>/dev/null
  say "完成。当前健康：$(gw_health)"
  audit "fix h=$(gw_health)"
  ;;
rescue)
  say "启动网关外自救（8 阶段）..."
  bash tools/desktop-rescue.sh 2>&1 | tail -25
  audit "rescue"
  ;;
services)
  for u in openclaw-gateway oc-gateway-watchdog.timer asr-ledger.timer dash-serve; do
    say "$(printf '%-28s' "$u") $(systemctl --user is-active "$u" 2>/dev/null)"
  done
  audit "services"
  ;;
logs)
  say "===== 网关最近日志 ====="
  journalctl --user -u openclaw-gateway --no-pager -n 25 2>/dev/null | sed 's/.*node\[[0-9]*\]: //' | cut -c1-150
  hr; say "===== 看门狗最近 ====="
  tail -8 "$WS/state/work/gateway-watchdog.log" 2>/dev/null | cut -c1-130
  audit "logs"
  ;;
diag)
  say "===== 诊断（保存到 state/diag）====="
  D="$WS/state/diag/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$D"
  { echo "== systemctl =="; systemctl --user status openclaw-gateway --no-pager -n 30;
    echo "== journal =="; journalctl --user -u openclaw-gateway --no-pager -n 120;
    echo "== mem =="; free -m; echo "== disk =="; df -h;
    echo "== config =="; cat /mnt/c/Users/J/.wslconfig 2>/dev/null; } > "$D/diag.txt" 2>&1
  say "已保存：$D/diag.txt"
  audit "$D"
  ;;
backups)
  say "===== 备份归档 ====="
  for d in /mnt/d /mnt/e /mnt/h; do
    say "-- $d"; ls -lht "$d/openclaw-backups"/*openclaw-backup.tar.gz 2>/dev/null | head -3 | awk '{print "   ", $5, $6, $7, $8, $9}'
  done
  audit "backups"
  ;;
backup-now)
  say "启动即时本地备份（只落 D 盘，不推送；约 60-80 分钟）..."
  U="backup-manual-$(date +%H%M%S)"
  systemd-run --user --unit="$U" --collect --property=TimeoutStartSec=infinity --setenv=PATH=/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin bash /home/j/.openclaw/workspace/tools/heartbeat-run.sh bash /home/j/.openclaw/workspace/tools/backup-with-quiet.sh bash /home/j/.openclaw/workspace/tools/backup-local.sh 2>&1 | tail -2
  say "已提交：$U"
  say "看进度：journalctl --user -u $U -f，或 tail -f state/work/bk-run.log"
  audit "backup-local $U"
  ;;
push-backup)
  say "推送最新归档到群晖 + 镜像 E/H（后台，约 20-40 分钟）..."
  U="backup-push-$(date +%H%M%S)"
  systemd-run --user --unit="$U" --collect --property=TimeoutStartSec=infinity --setenv=PATH=/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin bash /home/j/.openclaw/workspace/tools/backup-push-latest.sh 2>&1 | tail -2
  say "已提交：$U"
  say "看进度：journalctl --user -u $U -f，或 tail -f state/work/bk-run.log"
  audit "push-backup $U"
  ;;
cfgroll)
  ls -lt /home/j/.openclaw/openclaw.json.bak-* 2>/dev/null | head -10 | awk '{print $6, $7, $8, $9}'
  audit "cfgroll"
  ;;
cfgroll-apply)
  F="${1:-}"; [ -z "$F" ] && { say "用法: cfgroll-apply <备份文件名>"; exit 2; }
  cp "/home/j/.openclaw/$F" /home/j/.openclaw/openclaw.json && say "已恢复 $F"
  audit "apply=$F"
  ;;
clean-dry)
  say "磁盘清理预演（DRY）..."
  DRY=1 bash tools/disk-cleanup-all.sh 2>&1 | tail -20
  audit "clean-dry"
  ;;
quota)
  bash tools/model-econ.sh report 2>&1 | head -30
  audit "quota"
  ;;
brief)
  if [ -x tools/morning-brief.sh ]; then bash tools/morning-brief.sh 2>&1 | tail -40; else say "简报脚本缺失"; fi
  audit "brief"
  ;;
oc-status)
  timeout 60 openclaw status --no-color 2>&1 | head -60
  audit "oc-status"
  ;;
oc-health)
  timeout 30 openclaw health --no-color 2>&1 | head -40
  audit "oc-health"
  ;;
oc-logs)
  timeout 25 openclaw logs --no-color 2>&1 | head -80
  audit "oc-logs"
  ;;
oc-channels)
  timeout 30 openclaw channels list --no-color 2>&1 | head -40
  audit "oc-channels"
  ;;
oc-usage-table)
  timeout 90 openclaw status --usage --no-color 2>&1 | head -100
  audit "oc-usage-table"
  ;;
vhdx)
  bash tools/vhdx-status.sh 2>&1
  audit "vhdx"
  ;;
oc-today)
  timeout 120 python3 /home/j/openclaw-workspaces/work/proto/today-usage.py 2>&1
  audit "oc-today"
  ;;
*) say "未知命令: $CMD"; exit 2;;
esac
