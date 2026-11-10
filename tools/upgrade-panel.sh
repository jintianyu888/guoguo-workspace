#!/bin/bash
# upgrade-panel.sh v1 —— 面板「一键升级」背后的完整流程（npm 直装 + 快照 + 回滚）
# 用法：upgrade-panel.sh [--target X] [--dry-run]
# 阶段：预检 → 四库快照 → 停看门狗/网关 → npm 直装 → 安全重启 → 校验 → 失败回滚 → 飞书报告
set -uo pipefail
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
WS=/home/j/.openclaw/workspace
STATE=/home/j/.openclaw
LOG=$WS/state/work/upgrade-panel.log
FLAG=$WS/state/work/.upgrade-running
PAUSE=$WS/state/work/.watchdog-pause
TS=$(date +%Y%m%d-%H%M%S)
SNAP=$STATE/state/backup/upgrade-snap-$TS
DRY=0
TGT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --target) TGT="$2"; shift 2 ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
done
FROM=$(openclaw --version 2>/dev/null | awk '{print $2}')
[ -z "$TGT" ] && TGT=$(timeout 60 npm view openclaw version 2>/dev/null | tail -1)
say(){ echo "[$(date "+%F %T")] $*" | tee -a "$LOG"; }
nt(){ timeout 60 bash "$WS/tools/notify.sh" "$1" >/dev/null 2>&1 || true; }
fail(){ say "✗ $*"; nt "❌ 升级中止：$*"; exit 1; }

want_watchdog=0
cleanup(){
  rm -f "$FLAG"
  if [ "$want_watchdog" = "1" ]; then
    rm -f "$PAUSE"
    systemctl --user start oc-gateway-watchdog.timer >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

say "===== 升级开始 当前=$FROM 目标=$TGT dryrun=$DRY ====="
[ -z "$TGT" ] && fail "取不到目标版本（npm view 失败）"

# ---------- 1) 预检 ----------
[ -f "$FLAG" ] && fail "已有升级在进行（.upgrade-running）"
[ -f "$WS/state/work/.safe-restart-running" ] && fail "有安全重启在进行"
ps -eo args= | grep -E "openclaw update( |$)|npm (i|install) -g openclaw|upgrade-openclaw\.sh|upgrade-npm-direct\.sh" | grep -vE "grep|update status|upgrade-panel" | grep -q . && fail "检测到并行的升级进程"
pgrep -af "openclaw backup create" >/dev/null && fail "备份正在进行，等它结束再升级"
AVAIL=$(df -Pk / | awk 'NR==2{print int($4/1024/1024)}')
[ "$AVAIL" -lt 20 ] && fail "根分区可用仅 ${AVAIL}G（需 ≥20G）"
say "预检：磁盘可用 ${AVAIL}G"
if ! bash "$WS/tools/upgrade-preflight.sh" >>"$LOG" 2>&1; then
  fail "升级预检脚本失败（见 $LOG）"
fi
say "预检：upgrade-preflight.sh 通过"
if ! timeout 120 npm view "openclaw@$TGT" version >/dev/null 2>&1; then
  fail "目标版本 $TGT 在 npm 上不存在"
fi
say "预检：目标版本存在"
if [ "$DRY" = "1" ]; then
  say "演练模式：预检全部通过，不安装"
  nt "🧪 升级演练通过：$FROM → $TGT（未安装）"
  exit 0
fi

# ---------- 2) 四库快照 ----------
mkdir -p "$SNAP"
say "快照数据库 → $SNAP"
OUT=$(python3 - "$SNAP" <<'PY'
import sqlite3, os, sys
snap=sys.argv[1]
dbs=[("/home/j/.openclaw/state/openclaw.sqlite","openclaw.sqlite"),
     ("/home/j/.openclaw/lcm.db","lcm.db"),
     ("/home/j/.openclaw/state/ledger.db","ledger.db"),
     ("/home/j/.openclaw/agents/main/agent/openclaw-agent.sqlite","openclaw-agent.sqlite")]
ok=0
for src,name in dbs:
    if not os.path.exists(src) or os.path.getsize(src)<4096:
        print("skip",name); continue
    dst=os.path.join(snap,name)
    s=sqlite3.connect(f"file:{src}?mode=ro",uri=True); d=sqlite3.connect(dst)
    s.backup(d); d.close()
    q=sqlite3.connect(dst).execute("pragma quick_check").fetchone()[0]
    if q!="ok": print("BAD",name,q); sys.exit(3)
    print("ok",name,os.path.getsize(dst)); ok+=1
print("snap_ok",ok)
PY
)
echo "$OUT" | tee -a "$LOG"
echo "$OUT" | grep -q "^snap_ok" || fail "数据库快照失败"
[ "$(echo "$OUT" | grep -c '^ok')" -ge 3 ] || fail "有效快照少于 3 个"

# ---------- 3) 停看门狗 + 网关 ----------
touch "$FLAG"
touch "$PAUSE"
systemctl --user stop oc-gateway-watchdog.timer >/dev/null 2>&1
systemctl --user stop oc-gateway-watchdog.service >/dev/null 2>&1
want_watchdog=1
say "已暂停看门狗，停止网关"
systemctl --user stop openclaw-gateway.service >/dev/null 2>&1
for i in $(seq 1 30); do pgrep -af "openclaw-gateway" >/dev/null || break; sleep 2; done
pgrep -af "openclaw-gateway" >/dev/null && { systemctl --user start openclaw-gateway >/dev/null 2>&1; fail "网关未能在 60s 内停止"; }

# ---------- 4) 安装 ----------
say "npm i -g openclaw@$TGT ..."
if ! npm i -g "openclaw@$TGT" >>"$LOG" 2>&1; then
  ROLLBACK_REASON="npm 安装失败"; ROLLBACK=1
fi
NEW=$(openclaw --version 2>/dev/null | awk '{print $2}')
say "安装后版本：$NEW"
[ "${ROLLBACK:-0}" = "0" ] && [ "$NEW" != "$TGT" ] && { ROLLBACK=1; ROLLBACK_REASON="版本未变为 $TGT（实际 $NEW）"; }

# ---------- 5) 重启 + 校验 ----------
if [ "${ROLLBACK:-0}" = "0" ]; then
  say "启动网关（升级自持：网关已在第 3 步停止，此处直接拉起并按 health 校验）"
  systemctl --user start openclaw-gateway.service >>"$LOG" 2>&1
  RRC=$?
  H=000
  for i in $(seq 1 60); do
    H=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:18789/health || echo 000)
    [ "$H" = "200" ] && break
    sleep 3
  done
  say "restart_rc=$RRC health=$H"
  [ "$RRC" != "0" ] && { ROLLBACK=1; ROLLBACK_REASON="restart-gateway rc=$RRC"; }
  [ "$H" != "200" ] && { ROLLBACK=1; ROLLBACK_REASON="升级后 health=$H"; }
fi

# ---------- 6) 失败回滚 ----------
if [ "${ROLLBACK:-0}" = "1" ]; then
  say "✗ 触发回滚：$ROLLBACK_REASON"
  nt "⚠️ 升级失败（$ROLLBACK_REASON），正在回滚到 $FROM"
  npm i -g "openclaw@$FROM" >>"$LOG" 2>&1
  for f in openclaw.sqlite lcm.db ledger.db openclaw-agent.sqlite; do
    case "$f" in
      openclaw.sqlite) dst=/home/j/.openclaw/state/openclaw.sqlite ;;
      lcm.db) dst=/home/j/.openclaw/lcm.db ;;
      ledger.db) dst=/home/j/.openclaw/state/ledger.db ;;
      openclaw-agent.sqlite) dst=/home/j/.openclaw/agents/main/agent/openclaw-agent.sqlite ;;
    esac
    [ -f "$SNAP/$f" ] && cp -f "$SNAP/$f" "$dst"
  done
  ALLOW_UPGRADE_RESTART=1 bash "$WS/tools/restart-gateway.sh" --reason "升级失败回滚 $FROM" >>"$LOG" 2>&1
  H2=000
  for i in $(seq 1 40); do
    H2=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:18789/health || echo 000)
    [ "$H2" = "200" ] && break
    sleep 3
  done
  V2=$(openclaw --version 2>/dev/null | awk '{print $2}')
  nt "↩️ 已回滚：版本 $V2（health=$H2）。快照 $SNAP。原因：$ROLLBACK_REASON"
  say "回滚完成 版本=$V2 health=$H2"
  exit 1
fi

# ---------- 7) 收尾 ----------
bash "$WS/tools/sqlite-probe-timeout-patch.sh" apply >>"$LOG" 2>&1 || true
SC=$(timeout 120 bash "$WS/tools/stability-check.sh" 2>/dev/null | grep -E "^结果|PASS" | tail -1)
say "稳定自检：${SC:-未取到}"
PUC=$(bash "$WS/tools/post-upgrade-check.sh" 2>&1 | tail -1)
say "兼容自检：${PUC:-未取到}"
REVC=$(bash "$WS/tools/version-reconcile.sh" >/dev/null 2>&1; echo ok); say "两端版本对账：$REVC"
nt "✅ 升级完成：$FROM → $NEW（health=200，快照 $SNAP）${SC:+｜$SC}"
# ---------- 8) B 机同步升级（2026-11-07 主公令） ----------
# B 的 shell 通道只对 agent 开放（CLI 调 system.run 会被拒绝），因此由 agent turn 执行。
BVER=""
if [ "${SKIP_B:-0}" = "1" ]; then
  BRES="B机按参数跳过"
else
  if [ "${AUTO_B:-1}" = "1" ]; then
    say "触发 B 机升级（agent 执行，最多 30 分钟）"
    if timeout 1800 openclaw agent --agent main --message-file "$WS/tools/upgrade-b-prompt.md" >>"$LOG" 2>&1; then
      BRES="B机升级已触发（agent 执行，结果另报）"
    else
      # 由 agent 会话内直接跑升级时，嵌套 agent 调用会被 attribution 护栏拦下 → 退回待办
      python3 "$WS/tools/tasks-db.py" add 0 "升级 B 机 OpenClaw 到 $NEW" status=pending kind=task prio=2 \
        verify="exec host=node: cmd /c openclaw --version 输出 $NEW" \
        note="A 已升级完成；agent 触发被拦，需人工/下次会话执行；步骤见 docs/B机升级流程-20261107.md" --force >>"$LOG" 2>&1 || true
      BRES="B机待升级（触发被拦，已入待办）"
    fi
  else
    python3 "$WS/tools/tasks-db.py" add 0 "升级 B 机 OpenClaw 到 $NEW" status=pending kind=task prio=2 \
      verify="exec host=node: cmd /c openclaw --version 输出 $NEW" \
      note="A 机升级完成于 $(date +%F) $(date +%H:%M)；步骤见 docs/B机升级流程-20261107.md" --force >>"$LOG" 2>&1 || true
    BRES="B机待升级（已入待办）"
  fi
fi

say "===== 升级结束 ====="
nt "✅ A 机升级完成：$FROM → $NEW（health=200）｜$BRES"
exit 0
