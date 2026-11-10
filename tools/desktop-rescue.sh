#!/usr/bin/env bash
# desktop-rescue.sh —— 桌面"一键自救"的 WSL 侧执行体（2026-10-25 主公令）
# 场景：重启出问题 / 升级出问题 / 网关打不开时，人在 Windows 桌面双击 bat 即可自救。
# 设计原则：本脚本在网关进程之外运行，不依赖网关存活；只做恢复，不删数据、不改配置。
set -u
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace
D=$W/state/work/rescue
PORT=18789
PAT="dist/index.js gateway"
mkdir -p "$D"
TS=$(date +%Y%m%d-%H%M%S)
LOG="$D/rescue-$TS.log"
MODE=auto
case "${1:-}" in --deep) MODE=deep;; --force-restart) MODE=restart;; --auto|"") MODE=auto;; *) MODE=auto;; esac
: > "$LOG"; ln -sf "rescue-$TS.log" "$D/last.log" 2>/dev/null

say(){ printf '%s\n' "$*" | tee -a "$LOG"; }
ok(){  printf '  [OK] %s\n' "$*" | tee -a "$LOG"; }
bad(){ printf '  [!!] %s\n' "$*" | tee -a "$LOG"; }
info(){ printf '  ..   %s\n' "$*" | tee -a "$LOG"; }
hr(){ printf '%s\n' "------------------------------------------------------------" | tee -a "$LOG"; }
pid_of(){ pgrep -f "$PAT" | head -1; }
health(){ timeout 6 curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health" 2>/dev/null; }
is_up(){ [ "$(health)" = "200" ]; }
wait_up(){ local t=0; while [ "$t" -lt "$1" ]; do is_up && return 0; sleep 3; t=$((t+3)); done; return 1; }

hr; say "OpenClaw 自救程序  $(date '+%F %T')   模式=$MODE"; hr

# ---------- 第 0 步：地基 ----------
say "[0/5] 环境检查"
say "  系统: $(uname -sr)  主机: $(hostname)"
if ! systemctl --user is-system-running >/dev/null 2>&1; then
  bad "systemd 用户实例不可用 —— 自救程序无法管理网关服务"
  say "  → 请在 Windows 终端执行: wsl --shutdown  然后重新双击本程序"
  exit 4
fi
ok "systemd 用户实例正常"
SYSUP=$(systemctl --user is-system-running 2>/dev/null)
say "  服务状态: $SYSUP"

# ---------- 第 1 步：快照 ----------
say ""
say "[1/5] 采集现状"
ST=$(systemctl --user is-active openclaw-gateway 2>/dev/null)
PID=$(pid_of)
H=$(health)
say "  服务: $ST   进程PID: ${PID:-无}   /health: $H"
say "  systemd: $(systemctl --user show openclaw-gateway -p NRestarts -p Result -p ActiveState -p SubState --value 2>/dev/null | tr '\n' ' ')"
say "  资源: 内存$(free -h | awk '/Mem:/{print $3"/"$2}')  负载$(cut -d' ' -f1-3 /proc/loadavg)  磁盘根$(df -h / | awk 'NR==2{print $5}')"

if [ "$MODE" = "deep" ]; then
  say ""
  say "[深度诊断] 只读检查，不做任何改动"
  say "  配置校验: $(timeout 60 openclaw config validate 2>&1 | tail -1)"
  say "  版本: $(timeout 30 openclaw --version 2>&1 | head -1)"
  say "  失败单元:"; systemctl --user list-units --state=failed --no-legend 2>/dev/null | sed 's/^/    /' | tee -a "$LOG"
  say "  最近错误(20条):"
  journalctl --user -u openclaw-gateway --since '-30min' --no-pager 2>/dev/null | grep -iE 'error|fatal|failed|panic|EADDRINUSE' | tail -20 | sed 's/^/    /' | tee -a "$LOG"
  say "  计划任务可用: $(timeout 60 openclaw cron list --json >/dev/null 2>&1 && echo 是 || echo 否)"
  say ""; say "诊断完毕（未改动任何东西）。日志: $LOG"; exit 0
fi

if [ "$MODE" = "auto" ] && is_up && [ "$ST" = "active" ]; then
  ok "网关健康，无需自救"
  say ""
  say "[5/5] 顺带体检"
  say "  计划任务: $(timeout 60 openclaw cron list --json >/dev/null 2>&1 && echo 可读 || echo 不可读)"
  LV=$(ls -t "$W"/state/work/rescue/*.log 2>/dev/null | wc -l)
  say "  最近备份: $(ls -t /mnt/e/openclaw-backups/*.tar.gz 2>/dev/null | head -1 | xargs -r du -h 2>/dev/null | cut -f1)$(ls -t /mnt/e/openclaw-backups/*.tar.gz 2>/dev/null | head -1 | xargs -r date -r 2>/dev/null '+ %m-%d %H:%M')"
  say ""
  say "结果: 一切正常，不需要修。"; say "日志: $LOG"; exit 0
fi

# ---------- 第 2 步：重启/拉起 ----------
say ""
say "[2/5] 尝试拉起网关（原子 restart，不碰数据）"
systemctl --user reset-failed openclaw-gateway >/dev/null 2>&1
timeout 400 systemctl --user restart openclaw-gateway >>"$LOG" 2>&1
RC=$?
say "  restart 退出码: $RC"
if wait_up 120; then
  ok "已恢复  新PID=$(pid_of)  /health=200  用时约 $(( $(date +%s) - $(date -d '$TS' +%s 2>/dev/null || echo $(date +%s)) ))秒"
  RECOVERED=1
else
  bad "restart 后 120 秒未就绪"
  RECOVERED=0
fi

# ---------- 第 3 步：深度修复 ----------
if [ "$RECOVERED" = "0" ]; then
  say ""
  say "[3/5] 走 doctor --fix 自修复（在网关进程外执行）"
  timeout 600 openclaw doctor --fix >>"$LOG" 2>&1
  say "  doctor 退出码: $?"
  systemctl --user reset-failed openclaw-gateway >/dev/null 2>&1
  timeout 200 systemctl --user start openclaw-gateway >>"$LOG" 2>&1
  if wait_up 120; then
    ok "doctor 修复后恢复  新PID=$(pid_of)"
    RECOVERED=1
  else
    bad "doctor 也没救回来"
  fi
fi

# ---------- 第 4 步：证据包 ----------
if [ "$RECOVERED" = "1" ]; then
  say ""
  say "[4/5] 恢复后核验"
  say "  配置: $(timeout 60 openclaw config validate 2>&1 | tail -1)"
  say "  计划任务: $(timeout 90 openclaw cron list --json >/dev/null 2>&1 && echo 可读 || echo 不可读)"
  say "  版本: $(timeout 30 openclaw --version 2>&1 | head -1)"
  say ""
  say "结果: 自救成功。日志: $LOG"
  exit 0
fi

say ""
say "[4/5] 未恢复，生成证据包（供人工/模型分析）"
say "  --- 服务状态 ---"
systemctl --user status openclaw-gateway --no-pager -l 2>&1 | head -20 | sed 's/^/    /' | tee -a "$LOG"
say "  --- 最近日志 60 行 ---"
journalctl --user -u openclaw-gateway --since '-40min' --no-pager 2>/dev/null | tail -60 | sed 's/^/    /' | tee -a "$LOG"
say "  --- 配置 ---"
timeout 60 openclaw config validate 2>&1 | tail -5 | sed 's/^/    /' | tee -a "$LOG"
say "  --- 端口占用 ---"
(ss -ltnp 2>/dev/null | grep "$PORT" || echo "    端口 $PORT 无监听") | tee -a "$LOG"
say "  --- 资源 ---"
say "    $(free -h | awk '/Mem:/{print "内存 "$3"/"$2}')  $(df -h / | awk 'NR==2{print "根盘 "$5}')  $(df -h /home 2>/dev/null | awk 'NR==2{print "home "$5}')"

say ""
say "[5/5] 建议"
say "  1) 已自动尝试: restart → doctor --fix，均失败"
say "  2) 证据包: $LOG"
say "  3) 如果刚升级完就坏: 可能是版本问题，回滚命令（需人工确认后执行）:"
say "       npm install -g openclaw@<上一个可用版本> 然后重跑本程序"
say "  4) 日志里常见的三种死因: 端口 $PORT 被占 / 配置非法 / 内存不足被 OOM"
say ""
say "结果: 未能自动恢复，需要人工介入。"
exit 3
