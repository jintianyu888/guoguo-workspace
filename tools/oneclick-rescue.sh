#!/usr/bin/env bash
# oneclick-rescue.sh v5 — 桌面"一键自救" WSL 侧执行体（2026-10-26 主公令：一次点完，不再要人补动作）
# 不依赖网关存活；只做恢复与报告；仅在配置非法时从最近备份恢复。
set -u
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace
D=$W/state/work/rescue
PORT=18789
PAT="dist/index.js gateway"
UNIT=openclaw-gateway.service
mkdir -p "$D"
TS=$(date +%Y%m%d-%H%M%S)
LOG="$D/rescue-$TS.log"
MODE=auto; DRY=0
for a in "$@"; do case "$a" in --dry-run) DRY=1;; --deep) MODE=deep;; --force-restart) MODE=restart;; esac; done
say(){ printf "%s\n" "$*" | tee -a "$LOG"; }
hr(){ say "------------------------------------------------------------"; }
step(){ hr; say "[$1] $2"; }
fixed=0; warnn=0; failed=0
ok(){ say "  [OK] $*"; }
fx(){ say "  [FIX] $*"; fixed=$((fixed+1)); }
wn(){ say "  [WARN] $*"; warnn=$((warnn+1)); }
no(){ say "  [FAIL] $*"; failed=$((failed+1)); }
health(){ timeout 6 curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/health" 2>/dev/null; }
is_up(){ [ "$(health)" = "200" ]; }
pid_of(){ pgrep -f "$PAT" | head -1; }
wait_up(){ local s=$1 i=0; while [ $i -lt $s ]; do is_up && return 0; sleep 2; i=$((i+2)); done; return 1; }  # 参数=秒
say "OpenClaw 自救 v5 | $(date "+%F %T") | mode=$MODE dry=$DRY"
say "日志: $LOG"
step 1/8 "基础环境"
if timeout 10 systemctl --user is-system-running >/dev/null 2>&1; then ok "systemd user 可用"; else wn "systemd user 状态异常（继续尝试）"; fi
RO=$(df -P / | tail -1 | tr -s " " | cut -d" " -f5 | tr -d "%")
if [ "${RO:-0}" -ge 92 ]; then wn "根盘已用 ${RO}%"; else ok "根盘已用 ${RO}%"; fi
step 2/8 "清理陈旧状态"
for f in "$W/state/work/.safe-restart-running" "$W/state/work/.gateway-ctl.lock"; do
  if [ -e "$f" ]; then AGE=$(( $(date +%s) - $(stat -c %Y "$f" 2>/dev/null || echo 0) ));
    if [ "$AGE" -gt 600 ]; then if [ "$DRY" = 1 ]; then fx "将清理 $(basename "$f")（${AGE}s）"; else rm -f "$f"; fx "已清理 $(basename "$f")（${AGE}s）"; fi;
    else wn "$(basename "$f") 仅 ${AGE}s，保留"; fi; fi; done
Z=$(ps -eo stat 2>/dev/null | grep -c "^Z" || true); [ "${Z:-0}" -gt 0 ] && wn "僵尸进程 ${Z} 个" || ok "无僵尸进程"
step 3/8 "内存与 OOM"
MEMU=$(free | awk "/^Mem:/{printf \"%d\", \$3*100/\$2}")
[ "${MEMU:-0}" -ge 90 ] && wn "内存 ${MEMU}%" || ok "内存 ${MEMU}%"
OOM=$(dmesg 2>/dev/null | grep -ci "oom-kill" || true); [ "${OOM:-0}" -gt 0 ] && wn "OOM 记录 ${OOM} 条" || ok "无 OOM 记录"
step 4/8 "配置与端口"
if timeout 90 openclaw config validate >/dev/null 2>&1; then ok "配置合法"; else
  no "配置非法"; BEST=$(ls -t /home/j/.openclaw/openclaw.json.bak-* /home/j/.openclaw/openclaw.json.bak 2>/dev/null | head -1)
  if [ -n "${BEST:-}" ]; then if [ "$DRY" = 1 ]; then fx "将从备份恢复 $(basename "$BEST")"; else cp -f /home/j/.openclaw/openclaw.json "/home/j/.openclaw/openclaw.json.bad-$TS" 2>/dev/null || true; cp -f "$BEST" /home/j/.openclaw/openclaw.json; fx "已恢复 $(basename "$BEST")（坏配置留痕 openclaw.json.bad-$TS）"; timeout 90 openclaw config validate >/dev/null 2>&1 && ok "恢复后合法" || no "恢复后仍非法"; fi; else no "无配置备份"; fi; fi
OCC=$(ss -ltnp 2>/dev/null | grep ":$PORT " | head -1)
if [ -n "${OCC:-}" ]; then OPID=$(printf "%s" "$OCC" | grep -o "pid=[0-9]*" | head -1 | cut -d= -f2);
  if [ -n "${OPID:-}" ] && ps -p "$OPID" -o args= 2>/dev/null | grep -q "$PAT"; then ok "端口 $PORT 由网关占用"; elif is_up; then ok "端口 $PORT 有监听且 health=200（判定为网关）"; else wn "端口 $PORT 被占用但无法确认归属（非 root 抓不到 pid）: ${OCC}"; fi;
else ok "端口 $PORT 空闲"; fi
step 5/8 "拉起网关"
if is_up && [ "$MODE" != restart ]; then ok "网关已在运行 health=200 pid=$(pid_of)"; else
  if [ "$DRY" = 1 ]; then fx "将 reset-failed -> start -> 等 health"; else
    systemctl --user reset-failed "$UNIT" >/dev/null 2>&1 || true
    systemctl --user start "$UNIT" >/dev/null 2>&1 || systemctl --user restart "$UNIT" >/dev/null 2>&1 || true
    if wait_up 60; then fx "已拉起 pid=$(pid_of)"; else
      wn "首次未就绪，跑 doctor --fix 重试"; timeout 600 openclaw doctor --fix >>"$LOG" 2>&1 || true
      systemctl --user reset-failed "$UNIT" >/dev/null 2>&1 || true; systemctl --user restart "$UNIT" >/dev/null 2>&1 || true
      if wait_up 90; then fx "doctor 后拉起成功 pid=$(pid_of)"; else no "doctor 后仍未就绪"; fi; fi; fi; fi
step 6/8 "守护与代理"
for u in oc-gateway-watchdog.timer ollama-proxy.service; do ST=$(systemctl --user is-active "$u" 2>/dev/null || echo inactive);
  if [ "$ST" = active ]; then ok "$u 运行中"; else if [ "$DRY" = 1 ]; then fx "将启动 $u"; else systemctl --user start "$u" >/dev/null 2>&1 && fx "已启动 $u" || wn "$u 启动失败"; fi; fi; done
if timeout 6 curl -s -o /dev/null http://127.0.0.1:11434/api/tags 2>/dev/null; then ok "ollama 代理可用"; else wn "ollama 代理不可达（只影响本地模型）"; fi
if [ "$MODE" = deep ]; then
  step "6b/8" "深度检查"
  ERR=$(timeout 40 journalctl --user -u openclaw-gateway --since "2 hours ago" --no-pager 2>/dev/null | grep -ciE "error|fail" || true)
  [ "${ERR:-0}" -gt 200 ] && wn "近 2 小时日志错误行 ${ERR} 条（偏高）" || ok "近 2 小时日志错误行 ${ERR} 条"
  timeout 60 openclaw cron list --json >/dev/null 2>&1 && ok "计划任务可读" || wn "计划任务读不到（网关刚起可稍后重试）"
  for m in /mnt/e /mnt/h /mnt/x; do [ -d "$m" ] && { U=$(df -P "$m" | tail -1 | tr -s " " | cut -d" " -f5 | tr -d "%"); [ "${U:-0}" -ge 92 ] && wn "$m 已用 ${U}%" || ok "$m 已用 ${U}%"; }; done
fi

step 7/8 "消息通道"
if is_up; then CH=$(timeout 60 openclaw status --json 2>/dev/null | head -c 600); if printf "%s" "$CH" | grep -qi "connected\|running"; then ok "通道有已连接账号"; else wn "通道未确认（刚起可能仍在连，稍等再点一次）"; fi; else wn "网关未起，跳过"; fi
step 8/8 "结论"
say "  自动修复 $fixed 项 / 警告 $warnn 项 / 失败 $failed 项"
if is_up; then say "结果: 已恢复，网关 health=200 pid=$(pid_of)"; exit 0; else
  say "结果: 未能恢复（自动尝试已做尽）"; say "  证据: $LOG";
  say "  下一步: 重新双击桌面 OpenClaw一键自救 —— bat 会自动执行 wsl --shutdown 并重试，无需你手动敲命令";
  say "  若仍失败: 检查 X: 盘是否挂载（WSL 虚拟盘在 X:\\WSL\\Ubuntu）"; exit 3; fi
