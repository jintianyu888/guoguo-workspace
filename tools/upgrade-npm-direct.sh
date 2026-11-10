#!/bin/bash
# upgrade-npm-direct.sh v2 —— 绕过更新器 validating（探测 10s 硬超时）的 npm 直装升级
# 顺序：停看门狗+网关 → 四库快照 → npm 直装 → restart-gateway（含健康与迁移检查）→ 重打探测补丁
set -uo pipefail
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/upgrade-npm-direct.log
SNAP=/home/j/.openclaw/state/backup/upgrade-snap-$(date +%Y%m%d-%H%M%S)
TGT=2026.11.1
FROM=$(openclaw --version 2>/dev/null | awk '{print $2}')
say(){ echo "[$(date "+%F %T")] $*" | tee -a "$LOG"; }
nt(){ timeout 60 bash "$WS/tools/notify.sh" "$1" >/dev/null 2>&1 || true; }
restore_gw(){ rm -f "$WS/state/work/.watchdog-pause"; systemctl --user start oc-gateway-watchdog.timer 2>/dev/null; systemctl --user start openclaw-gateway 2>/dev/null; }
say "开始：$FROM -> $TGT"
# 1) 停看门狗 + 网关
touch "$WS/state/work/.watchdog-pause"
systemctl --user stop oc-gateway-watchdog.timer 2>/dev/null
systemctl --user stop openclaw-gateway 2>/dev/null
sleep 6
# 2) 四库快照
mkdir -p "$SNAP"
for f in /home/j/.openclaw/openclaw.sqlite /home/j/.openclaw/lcm.db /home/j/.openclaw/ledger.db /home/j/.openclaw/openclaw-agent.sqlite; do
  b=$(basename "$f")
  if ! python3 - "$f" "$SNAP/$b" >>"$LOG" 2>&1 <<'PY'
import sqlite3,sys
src,dst=sys.argv[1],sys.argv[2]
sqlite3.connect(src).backup(sqlite3.connect(dst))
PY
  then say "快照失败 $b"; restore_gw; nt "❌ 升级中止：$b 快照失败（网关已拉起）"; exit 1; fi
  q=$(python3 -c "import sqlite3,sys;print(sqlite3.connect(sys.argv[1]).execute('PRAGMA quick_check;').fetchone()[0])" "$SNAP/$b" 2>/dev/null)
  if [ "$q" != "ok" ]; then say "快照校验失败 $b ($q)"; restore_gw; nt "❌ 升级中止：$b 快照校验失败（网关已拉起）"; exit 1; fi
  say "快照 $b $(du -h "$SNAP/$b" | cut -f1) ok"
done
# 3) npm 直装
say "npm i -g openclaw@$TGT"
npm i -g "openclaw@$TGT" --no-fund --no-audit >>"$LOG" 2>&1; RC=$?
V=$(openclaw --version 2>/dev/null | awk '{print $2}')
say "安装 rc=$RC 版本=$V"
if [ "$RC" != "0" ] || [ "$V" != "$TGT" ]; then
  say "安装失败，回滚 $FROM"
  npm i -g "openclaw@$FROM" --no-fund --no-audit >>"$LOG" 2>&1
  for b in openclaw.sqlite lcm.db ledger.db openclaw-agent.sqlite; do [ -f "$SNAP/$b" ] && cp -f "$SNAP/$b" "/home/j/.openclaw/$b"; done
  restore_gw; sleep 15
  nt "❌ 直装升级失败，已回滚 $FROM（rc=$RC）。日志 $LOG"
  exit 1
fi
# 4) 启动网关（官方闸门：健康等待 + 迁移检查）
rm -f "$WS/state/work/.watchdog-pause"
systemctl --user start oc-gateway-watchdog.timer 2>/dev/null
bash "$WS/tools/restart-gateway.sh" --reason "npm 直装升级 $TGT" >>"$LOG" 2>&1; RRC=$?
sleep 6
H=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://127.0.0.1:18789/health)
say "升级后 health=$H restart_rc=$RRC 版本=$(openclaw --version 2>/dev/null | awk '{print $2}')"
# 5) 重打探测超时补丁（备份用；已无升级待办，不影响校验）
bash "$WS/tools/sqlite-probe-timeout-patch.sh" apply >>"$LOG" 2>&1
if [ "$H" = "200" ]; then
  nt "✅ 升级完成：$V（health=200）。备份探测补丁已重打，稍后跑全量备份实证。"
else
  nt "⚠️ 升级后 health=$H（版本 $V），请查 $LOG"
fi
say "结束"
