#!/usr/bin/env bash
# upgrade-openclaw.sh v1.1 (2026-11-05) —— 果果助手「升级」按钮唯一执行体
# 流程：预检 → 备份快照 → 安装 → 重启 → 硬验证 → 自检对齐 → 报告
# 用法：bash tools/upgrade-openclaw.sh [--dry-run | --postcheck-only]
set -u
WS=/home/j/.openclaw/workspace
OH=/home/j/.openclaw
PORT=18789
TS=$(date +%Y%m%d-%H%M%S)
BK="$OH/state/backup/upgrade-$TS"
LEDGER="$WS/state/work/upgrade-ledger.jsonl"
UPFLAG="$WS/state/work/.upgrade-running"
DBLIST="$OH/state/openclaw.sqlite $OH/lcm.db $WS/state/ledger/ledger.db $OH/agents/main/agent/openclaw-agent.sqlite"
MODE=upgrade
[ "${1:-}" = "--dry-run" ] && MODE=dryrun
[ "${1:-}" = "--postcheck-only" ] && MODE=postcheck

say(){ printf "[%s] %s\n" "$(date +%H:%M:%S)" "$*"; }
hr(){ echo "---------------------------------------------"; }
note(){ printf '{"ts":"%s","stage":"%s","msg":"%s"}\n' "$TS" "$1" "$(printf %s "$2" | tr -d '"')" >> "$LEDGER"; }
die(){ say "✗ 中止：$*"; note abort "$*"; rm -f "$WS/state/work/.upgrade-running"; exit 1; }
ver(){ timeout 120 openclaw --version 2>/dev/null | tail -1 | awk '{print $2}'; }
latest(){ timeout 45 npm view openclaw version 2>/dev/null | tail -1; }
health(){ [ "$(timeout 10 curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health" 2>/dev/null)" = "200" ]; }
schemaver(){ timeout 20 python3 "$WS/tools/upgrade-dbcheck.py" schema 2>/dev/null; }
migfail(){ timeout 20 python3 "$WS/tools/upgrade-dbcheck.py" migfail 2>/dev/null; }
dbwrite(){ timeout 30 python3 "$WS/tools/upgrade-dbcheck.py" write >/dev/null 2>&1; }
acount(){ timeout 90 openclaw agents list --json 2>/dev/null | python3 -c 'import json,sys;d=json.load(sys.stdin);print(len(d if isinstance(d,list) else d.get("agents",[])))' 2>/dev/null; }
ccount(){ timeout 90 openclaw cron list --json 2>/dev/null | python3 -c 'import json,sys;d=json.load(sys.stdin);j=d if isinstance(d,list) else d.get("jobs",[]);print(len(j))' 2>/dev/null; }
waithealth(){ i=0; while [ $i -lt 100 ]; do health && return 0; sleep 3; i=$((i+1)); done; return 1; }

rollback(){
  hr; say "↩ 回滚到 $CUR"
  timeout 600 npm install -g "openclaw@$CUR" >/dev/null 2>&1; say "  装回旧版 rc=$? 版本=$(ver)"
  rm -f "$UPFLAG" "$WS/state/work/.watchdog-pause"
  systemctl --user stop openclaw-gateway >/dev/null 2>&1; sleep 6
  python3 - "$BK" $DBLIST <<'PY'
import sys, os, shutil
bk = sys.argv[1]
for dst in sys.argv[2:]:
    src = os.path.join(bk, os.path.basename(dst))
    if not os.path.exists(src):
        print("  跳过(无快照)", dst)
        continue
    for suf in ("-wal", "-shm"):
        p = dst + suf
        if os.path.exists(p):
            os.remove(p)
    shutil.copy2(src, dst)
    print("  还原", os.path.basename(dst), "%.1fMB" % (os.path.getsize(dst) / 1048576))
PY
  systemctl --user start openclaw-gateway >/dev/null 2>&1
  if waithealth; then
    say "  回滚后健康 OK：版本 $(ver) schema $(schemaver)"
    note rollback "to $CUR ok"
  else
    say "  ✗ 回滚后仍不健康，需人工介入；备份在 $BK"
    note rollback "to $CUR FAILED"
  fi
  exit 1
}

do_upgrade(){
say "===== OpenClaw 升级 ====="
CUR=$(ver); [ -n "$CUR" ] || die "读不到当前版本"
say "当前版本 $CUR"
TGT=$(latest); [ -n "$TGT" ] || die "查不到最新版本（npm 不通）"
say "目标版本 $TGT"
if [ "$CUR" = "$TGT" ]; then say "已是最新，无需升级"; note uptodate "$CUR"; exit 0; fi

hr; say "① 预检"
FREE=$(df -Pm /home/j | tail -1 | awk '{print $4}')
say "  磁盘可用 ${FREE}MB"; [ "${FREE:-0}" -ge 6000 ] || die "磁盘不足 6GB"
if health; then say "  /health 200"; else die "网关当前不健康，先点「一键修复」"; fi
if dbwrite; then say "  真写探测通过"; else die "数据库写不进去，先修库"; fi
[ -f "$WS/state/work/.safe-restart-running" ] && die "有安全重启在进行，等它结束再来"
[ -f "$WS/state/work/.watchdog-pause" ] && die "存在看门狗暂停开关 state/work/.watchdog-pause，确认后删除再升级"
# 2026-11-05 23:21 修正：原 pgrep -af 会把调用方 bash 包装进程误判为升级进程
[ -f "$WS/state/work/.upgrade-running" ] && die "已有升级在跑（标志文件）"
# 孤儿标志：无真实升级进程时自动清掉
if [ -f "$WS/state/work/.upgrade-running" ] && ! pgrep -x node -a 2>/dev/null | grep -q "openclaw (update|upgrade)"; then
  say "  （清理孤儿标志 .upgrade-running）"; rm -f "$WS/state/work/.upgrade-running"
fi
BUSY=$(pgrep -a -x node 2>/dev/null | grep -E "openclaw (update|upgrade)"; pgrep -a -x npm 2>/dev/null | grep -E "(i|install) -g openclaw")
[ -n "$BUSY" ] && die "已有升级进程在跑：$BUSY"
SCV=$(timeout 240 bash "$WS/tools/console-cmd.sh" selfcheck 2>&1 | grep -o 'PASS [0-9]* / WARN [0-9]* / FAIL [0-9]*' | tail -1)
say "  自检 $SCV"
case "$SCV" in
  *"FAIL 0"*) PN=$(printf %s "$SCV" | sed -n 's/.*PASS \([0-9]*\) .*/\1/p'); if [ -z "$PN" ] || [ "$PN" -lt 10 ]; then die "自检通过项偏少（$SCV）"; fi ;;
  *) die "自检未通过或结果不可信（$SCV）" ;;
esac
BASE_SCHEMA=$(schemaver); BASE_AG=$(acount); BASE_CR=$(ccount); MIG_BASE=$(migfail); MIG_BASE=${MIG_BASE:-0}
say "  基线：schema $BASE_SCHEMA／agent $BASE_AG／cron $BASE_CR"
[ -n "$BASE_SCHEMA" ] && [ -n "$BASE_AG" ] && [ -n "$BASE_CR" ] || die "基线读数失败，不敢动"

hr; say "② 备份快照 → $BK"
mkdir -p "$BK" || die "建备份目录失败"
cp "$OH/openclaw.json" "$BK/openclaw.json" && say "  配置已备份"
python3 - "$BK" $DBLIST <<'PY'
import sqlite3, sys, os
bk = sys.argv[1]
bad = 0
for src in sys.argv[2:]:
    if not os.path.exists(src):
        print("  跳过(不存在)", src)
        continue
    dst = os.path.join(bk, os.path.basename(src))
    try:
        c = sqlite3.connect(src, timeout=30)
        try:
            c.execute("pragma wal_checkpoint(TRUNCATE)")
        except Exception:
            pass
        d = sqlite3.connect(dst)
        c.backup(d)
        d.close()
        q = sqlite3.connect(dst).execute("pragma quick_check").fetchone()[0]
        sz = os.path.getsize(dst) / 1048576
        print("  %-32s %7.1fMB quick_check=%s" % (os.path.basename(src), sz, q))
        if q != "ok" or sz < 0.01:
            bad += 1
        c.close()
    except Exception as e:
        print("  ✗ 失败", src, e)
        sys.exit(1)
sys.exit(1 if bad else 0)
PY
[ $? -eq 0 ] || die "数据库快照失败，未做任何改动"
note snapshot "$BK"

if [ "$MODE" = dryrun ]; then say "（dry-run 到此为止）备份在 $BK"; note dryrun "$BK"; exit 0; fi

hr; say "③ 安装 $TGT（网关会短暂中断）"
touch "$UPFLAG"
touch "$WS/state/work/.watchdog-pause"
PAUSED=1
trap '[ "${PAUSED:-0}" = 1 ] && rm -f "$WS/state/work/.watchdog-pause"' EXIT
note install "start $TGT"
timeout 1200 openclaw update --yes 2>&1 | tail -30
RC=${PIPESTATUS[0]}
rm -f "$UPFLAG"
if [ "$RC" -ne 0 ]; then say "✗ 安装失败 rc=$RC，当前版本=$(ver)"; rollback; fi
VAFTER=$(ver); if [ "$VAFTER" != "$TGT" ]; then say "✗ 装完版本仍是 $VAFTER（期望 $TGT）"; rollback; fi
say "  安装完成 rc=0，版本 $VAFTER"

hr; say "④ 重启网关"
rm -f "$WS/state/work/.watchdog-pause"
bash "$WS/tools/restart-gateway.sh" --reason "升级到 $TGT" 2>&1 | tail -6
if waithealth; then say "  /health 200"; else say "✗ 重启后不健康"; rollback; fi

hr; say "⑤ 硬验证"
sleep 8
NEWV=$(ver); SC=$(schemaver); AG=$(acount); CR=$(ccount); MF=$(migfail)
say "  版本 $NEWV／schema $SC／agent $AG／cron $CR／失败迁移 $MF"
FAILS=""
[ "$NEWV" = "$TGT" ] || FAILS="$FAILS 版本不符($NEWV)"
[ "${SC:-0}" -ge "${BASE_SCHEMA:-0}" ] 2>/dev/null || FAILS="$FAILS schema未前进($SC)"
[ "${AG:-0}" -ge "${BASE_AG:-0}" ] 2>/dev/null || FAILS="$FAILS agent少($AG<$BASE_AG)"
[ "${CR:-0}" -ge "${BASE_CR:-0}" ] 2>/dev/null || FAILS="$FAILS cron少($CR<$BASE_CR)"
[ "${MF:-999}" -le "${MIG_BASE:-0}" ] 2>/dev/null || FAILS="$FAILS 新增失败迁移($MF>$MIG_BASE)"
dbwrite || FAILS="$FAILS 真写失败"
if [ -n "$FAILS" ]; then say "✗ 验证不通过：$FAILS"; rollback; fi
say "  ✓ 硬验证通过"
}

postcheck(){
hr; say "⑥ 自检对齐"
TSTAMP=$(date +%Y%m%d-%H%M%S)
REPORT="$WS/state/work/upgrade-report-$TSTAMP.md"
CV=$(timeout 120 openclaw config validate 2>&1 | tail -1)
say "  配置校验：$CV"
SC2=$(timeout 300 bash "$WS/tools/console-cmd.sh" selfcheck 2>&1 | grep -o 'PASS [0-9]* / WARN [0-9]* / FAIL [0-9]*' | tail -1)
say "  运行自检：$SC2"
timeout 200 python3 "$WS/tools/schedule-audit.py" >/tmp/sa.out 2>&1
SARC=$?
say "  时间表对齐：rc=$SARC $(tail -1 /tmp/sa.out 2>/dev/null | cut -c1-60)"
TMR=""
for u in oc-gateway-watchdog.timer sqlite-hygiene.timer oc-restart-daily.timer; do
  st=$(systemctl --user is-active "$u" 2>/dev/null)
  TMR="$TMR $u=$st"
done
say "  定时器：$TMR"
C2=$(acount); R2=$(ccount); M2=$(migfail)
{
  echo "# 升级报告 $TSTAMP"
  echo "- 版本：$CUR → $(ver)"
  echo "- schema：${BASE_SCHEMA:-?} → $(schemaver)"
  echo "- agent：${BASE_AG:-?} → $C2；cron：${BASE_CR:-?} → $R2；失败迁移：$M2"
  echo "- 配置校验：$CV"
  echo "- 运行自检：$SC2"
  echo "- 时间表对齐：rc=$SARC"
  echo "- 定时器：$TMR"
  echo "- 备份：$BK"
  echo "- 控制台日志：$WS/state/work/upgrade-console.log"
} > "$REPORT"
say "  报告：$REPORT"
case "$SC2" in
  *"FAIL 0"*) say "  ✓ 自检无 FAIL" ;;
  *) say "  ⚠ 自检有 FAIL（不自动回滚，记待处理）：$SC2"; note selfcheck "FAIL $SC2" ;;
esac
[ "$SARC" -eq 0 ] || { say "  ⚠ 时间表对齐异常 rc=$SARC，见 /tmp/sa.out"; note schedule "rc=$SARC"; }
if [ -f "$WS/state/work/pending-x" ]; then
  say "→ 有归档待落 X 盘，后台补拷"
  systemd-run --user --unit="xcopy-after-upgrade-$(date +%H%M%S)" --collect --property=TimeoutStartSec=infinity --setenv=PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin bash "$WS/tools/x-copy-latest.sh" >/dev/null 2>&1 || say "  （X 盘补拷提交失败）"
  rm -f "$WS/state/work/pending-x"
fi

if [ -f "$WS/state/work/pending-mirror" ]; then
  say "→ 有归档待镜像，后台做 E/H 镜像+校验"
  systemd-run --user --unit="mirror-after-upgrade-$(date +%H%M%S)" --collect --property=TimeoutStartSec=infinity --setenv=PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin bash "$WS/tools/backup-mirror-verify.sh" >/dev/null 2>&1 || say "  （镜像提交失败）"
  rm -f "$WS/state/work/pending-mirror"
fi

if [ -f "$WS/state/work/pending-backup-push" ]; then
  say "→ 有本地备份待推送，后台推送 E/H/群晖"
  systemd-run --user --unit="backup-push-after-upgrade-$(date +%H%M%S)" --collect --property=TimeoutStartSec=infinity --setenv=PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin bash "$WS/tools/backup-push-latest.sh" >/dev/null 2>&1 || say "  （推送提交失败，稍后手动点「推送」）"
fi

if [ "$MODE" = upgrade ]; then timeout 60 bash "$WS/tools/notify.sh" "OpenClaw 升级完成：$CUR → $(ver)；自检 $SC2；对齐 rc=$SARC；报告 state/work/upgrade-report-$TSTAMP.md" >/dev/null 2>&1 || say "  （飞书通知失败，不影响升级）"; fi
note postcheck "selfcheck=$SC2 schedule_rc=$SARC"
}

if [ "$MODE" = postcheck ]; then
  say "===== 只做自检对齐（不升级）====="
  CUR=$(ver); BASE_SCHEMA=$(schemaver); BASE_AG=$(acount); BASE_CR=$(ccount); BK="(未做备份)"
  postcheck
  exit 0
fi

do_upgrade
postcheck
say "✓ 升级完成：$CUR → $(ver)（schema $(schemaver)，agent $(acount)，cron $(ccount)）"
say "   备份保留在 $BK"
note done "$CUR->$(ver)"
exit 0
