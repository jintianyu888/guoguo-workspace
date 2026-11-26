#!/bin/bash
# rollback-1110.sh —— 回滚 OpenClaw 11.10 → 11.9（主公 2026-11-26 19:23 批准）
set -uo pipefail
export PATH=/usr/bin:/bin:/home/j/.npm-global/bin:/usr/local/bin
W=/home/j/.openclaw/workspace
OH=/home/j/.openclaw
LOG=$W/state/work/rollback-1110.log
TS=$(date +%Y%m%d-%H%M%S)
BK=$OH/state/backup/rollback-$TS
TGT=2026.11.9
CUR=$(openclaw --version 2>/dev/null | grep -oE '[0-9]{4}\.[0-9]+\.[0-9]+' | head -1)
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
fail_notify(){ timeout 60 bash "$W/tools/notify.sh" "$1" >/dev/null 2>&1 || true; }

say "===== 回滚开始 当前=$CUR 目标=$TGT ====="
mkdir -p "$BK"
say "① 快照库（backup API）→ $BK"
python3 "$W/tools/snapshot-dbs.py" "$BK"
if [ $? -ne 0 ]; then say "✗ 快照失败，中止"; fail_notify "【回滚中止】库快照失败，未改动"; exit 1; fi

say "② 暂停看门狗 + 停网关"
systemctl --user stop oc-gateway-watchdog.timer 2>/dev/null
touch "$W/state/work/.watchdog-pause"
systemctl --user stop openclaw-gateway.service 2>/dev/null
sleep 3
say "  网关状态=$(systemctl --user is-active openclaw-gateway.service)"

say "③ 安装 $TGT"
timeout 900 npm install -g "openclaw@$TGT" >/tmp/rb-npm.log 2>&1
NEW=$(openclaw --version 2>/dev/null | grep -oE '[0-9]{4}\.[0-9]+\.[0-9]+' | head -1)
say "  装后版本=$NEW"
if [ "$NEW" != "$TGT" ]; then
  say "✗ 未达目标，装回 $CUR 并启动"
  timeout 900 npm install -g "openclaw@$CUR" >>/tmp/rb-npm.log 2>&1
  bash "$W/tools/gw-start-guard.sh" >>"$LOG" 2>&1 || true
  rm -f "$W/state/work/.watchdog-pause"
  systemctl --user start oc-gateway-watchdog.timer 2>/dev/null
  fail_notify "【回滚失败】未能装上 $TGT，已装回 $CUR 并启动；详见 $LOG"
  exit 1
fi

say "④ 启动（唯一托管路径）"
bash "$W/tools/gw-start-guard.sh" >>"$LOG" 2>&1
sleep 5
H=$(timeout 10 curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/health)
say "  health=$H"

say "⑤ 校验"
if bash "$W/tools/db-integrity-gate.sh" >>"$LOG" 2>&1; then DBOK=ok; else DBOK=BAD; fi
AG=$(timeout 90 openclaw agents list --json 2>/dev/null | python3 "$W/tools/count-json.py")
CR=$(timeout 90 openclaw cron list --json 2>/dev/null | python3 "$W/tools/count-json.py")
REENTRY=$(journalctl --user -u openclaw-gateway --since "2 min ago" --no-pager 2>/dev/null | grep -c "plugin load reentry")
say "  库=$DBOK agent=$AG cron=$CR reentry=$REENTRY health=$H"

{
  echo "# 回滚 11.10 → 11.9 报告 $TS"
  echo "- 原版本：$CUR；回滚后：$NEW"
  echo "- health：$H；库完整性：$DBOK；agent：$AG；cron：$CR"
  echo "- plugin load reentry（2 分钟内）：$REENTRY（11.10 时每小时上千次）"
  echo "- 库快照：$BK"
  echo "- 版本禁用名单已含 2026.11.10：state/work/upgrade-deny.json"
  echo "- 日志：$LOG"
} > "$W/state/work/rollback-1110-report.md"

rm -f "$W/state/work/.watchdog-pause"
systemctl --user start oc-gateway-watchdog.timer 2>/dev/null
say "===== 回滚结束 ====="

if [ "$H" = "200" ] && [ "$DBOK" = "ok" ]; then
  fail_notify "【回滚完成】11.10→$NEW 成功｜health 200｜库 ok｜agent $AG｜cron $CR｜reentry $REENTRY（此前每小时上千次）｜报告 state/work/rollback-1110-report.md"
  exit 0
fi
fail_notify "【回滚异常】11.10→$NEW：health=$H 库=$DBOK，需人工看 $LOG"
exit 1
