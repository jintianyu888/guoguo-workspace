#!/bin/bash
# autofix.sh —— 一键自检 + 自动修复（2026-10-29 主公令）
# 只做安全、可回滚的修复；涉及密钥/删除/权限的一律只报不动
set -u
export PATH=/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace; cd "$W" || exit 3
LOG=$W/state/work/autofix.log
say(){ printf '%s %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG"; }
notify(){ timeout 60 bash "$W/tools/notify.sh" "$1" >/dev/null 2>&1 || true; }
H(){ timeout 6 curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/health 2>/dev/null || echo 000; }

say "===== 自检开始 ====="
OUT=$(timeout 240 bash "$W/tools/console-cmd.sh" selfcheck 2>&1)
printf '%s\n' "$OUT" | grep -E '❌|⚠️' | sed 's/^/  发现: /' | tee -a "$LOG"
FIXED=0; SKIP=0

# 1) 服务未启动
if ! systemctl --user is-active openclaw-gateway >/dev/null 2>&1; then
  say "修复: 启动网关服务"; systemctl --user start openclaw-gateway && FIXED=$((FIXED+1)); sleep 8
fi
# 2) 单元未 enable（重启后不自启）
if [ "$(systemctl --user is-enabled openclaw-gateway 2>/dev/null)" != "enabled" ]; then
  say "修复: 设置开机自启"; systemctl --user enable openclaw-gateway >/dev/null 2>&1 && FIXED=$((FIXED+1))
fi
# 3) 健康端点
for i in 1 2 3; do [ "$(H)" = "200" ] && break; sleep 10; done
# 评审修正：必须连续两次异常才重启，避免抖动误伤；重启后核验 PID 换新
if [ "$(H)" != "200" ]; then
  sleep 10; H2=$(H)
else H2=200; fi
if [ "$H2" != "200" ]; then
  say "修复: 健康连续异常($H2)，走受控重启"
  OLD=$(systemctl --user show -p MainPID --value openclaw-gateway 2>/dev/null)
  bash "$W/tools/restart-gateway.sh" --reason "一键自检自动修复：健康端点连续异常" >/dev/null 2>&1; RG_RC=$?
  if [ "$RG_RC" -ne 0 ]; then
    if [ "$RG_RC" -eq 4 ]; then say "重启被安全门禁拦下(rc=4：静默窗/升级中/已有重启)，不算故障"
    else say "重启提交失败(rc=$RG_RC)"; notify "【一键自检】重启提交失败 rc=$RG_RC"; fi
  fi
  for i in $(seq 1 30); do
    sleep 10
    NEW=$(systemctl --user show -p MainPID --value openclaw-gateway 2>/dev/null)
    [ "$(H)" = "200" ] && [ -n "$NEW" ] && [ "$NEW" != "0" ] && [ "$NEW" != "$OLD" ] && break
  done
  if [ "$(H)" != "200" ] || [ -z "$NEW" ] || [ "$NEW" = "0" ] || [ "$NEW" = "$OLD" ]; then
    say "重启未生效（健康=$(H) PID $OLD→$NEW），交看门狗"; notify "【一键自检】自动重启未生效（健康=$(H)，PID $OLD→$NEW），需人工介入"
  else
    say "重启已生效：PID $OLD→$NEW 健康 200"
    [ "$RG_RC" -eq 0 ] && FIXED=$((FIXED+1))
  fi
fi
# 4) 看门狗定时器
if ! systemctl --user is-active oc-gateway-watchdog.timer >/dev/null 2>&1; then
  say "修复: 重启看门狗定时器"
  systemctl --user enable --now oc-gateway-watchdog.timer >/dev/null 2>&1 && FIXED=$((FIXED+1))
fi
# 5) 崩溃后自启的每日窗口定时器
if ! systemctl --user is-active oc-restart-daily.timer >/dev/null 2>&1; then
  say "修复: 恢复每日重启窗口定时器"
  systemctl --user enable --now oc-restart-daily.timer >/dev/null 2>&1 && FIXED=$((FIXED+1))
fi
# 6) ASR 卡锁
if [ -f /home/j/.cache/asr.lock ]; then
  AGE=$(( ( $(date +%s) - $(stat -c %Y /home/j/.cache/asr.lock) ) / 60 ))
  # 评审修正：只有锁很旧且确实没有转写进程在跑时才清
  if [ "$AGE" -gt 30 ] && ! pgrep -f "tools/asr|whisper-wrapper" >/dev/null 2>&1; then
    say "修复: 清理僵尸 ASR 锁（${AGE}分钟，无转写进程）"; mv -f /home/j/.cache/asr.lock /tmp/asr.lock.stale.$(date +%s) && FIXED=$((FIXED+1))
  elif [ "$AGE" -gt 30 ]; then say "ASR 锁 ${AGE} 分钟但有转写进程在跑，不动"; fi
fi
# 7) 卡住的看门狗/重启标记
for f in state/work/.safe-restart-running state/work/.upgrade-running; do
  if [ -f "$f" ]; then
    AGE=$(( ( $(date +%s) - $(stat -c %Y "$f") ) / 60 ))
    [ "$AGE" -gt 30 ] && { say "修复: 清理陈旧标记 $f（${AGE}分钟）"; rm -f "$f" && FIXED=$((FIXED+1)); }
  fi
done
# 8) 内存压力（>90% 且允许重启）
RSSM=$(systemctl --user show -p MemoryCurrent --value openclaw-gateway 2>/dev/null)
CAP=36
if [ -n "${RSSM:-}" ] && [ "$RSSM" != "[not set]" ]; then
  G=$(( RSSM / 1024 / 1024 / 1024 ))
  if [ "$G" -ge 30 ]; then say "修复: 网关内存 ${G}G 过高，安排受控重启";
    bash "$W/tools/restart-gateway.sh" --reason "一键自检自动修复：内存${G}G" >/dev/null 2>&1 && FIXED=$((FIXED+1)); sleep 25; fi
fi
# 9) 只报不修的
printf '%s\n' "$OUT" | grep -q '明文' && { say "待主公: 存在明文密钥（需本人决定是否迁移）"; SKIP=$((SKIP+1)); }

say "----- 复检 -----"
OUT2=$(timeout 240 bash "$W/tools/console-cmd.sh" selfcheck 2>&1)
V=$(printf '%s\n' "$OUT2" | grep -o 'PASS [0-9]* / WARN [0-9]* / FAIL [0-9]*' | tail -1)
say "复检结论: ${V:-未取到}（本次修复 $FIXED 项，需主公 $SKIP 项）"
printf '%s\n' "$OUT2" | grep -E '❌' | sed 's/^/  剩余: /' | tee -a "$LOG"
notify "【一键自检】${V:-未取到}；自动修复 $FIXED 项；需主公处理 $SKIP 项。详见 果果助手 → 日志"
say "===== 自检结束 ====="
