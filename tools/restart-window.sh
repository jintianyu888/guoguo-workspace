#!/bin/bash
# restart-window.sh —— 每日 08:00 统一重启窗口（2026-10-29 主公令；2026-10-31 改为 08:00）
# 流程：自检 -> 全绿才重启 -> 重启后复检 -> 处理重启队列 -> 飞书报备
# 用法: bash tools/restart-window.sh [--dry-run]   （RW_FORCE=1 绕过今日去重，用于手动补跑）
set -u
export PATH=/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace
cd "$W" || exit 3
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
Q=$W/state/work/restart-queue.md
LOG=$W/state/work/restart-window.log
mkdir -p "$(dirname "$LOG")"
say(){ printf '%s %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG"; }
notify(){ timeout 60 bash "$W/tools/notify.sh" "$1" >/dev/null 2>&1 || true; }

say "===== 重启窗口开始 dry=$DRY ====="

# 0) 冲突检查
for f in .upgrade-running .safe-restart-running .watchdog-pause; do
  [ -f "$W/state/work/$f" ] && { say "跳过：存在 $f"; exit 0; }
done
HHMM=$(date +%H%M)
if [ "$HHMM" -ge 400 ] && [ "$HHMM" -le 605 ]; then say "跳过：处于备份离线窗 04:00-06:05"; exit 0; fi

# 0.5) 去重：今早 08:00 后已升级/重启过且健康 → 本窗口只体检不重启（2026-10-30 双审修正，防双重启）
MAINPID=$(systemctl --user show -p MainPID --value openclaw-gateway 2>/dev/null)
if [ -n "$MAINPID" ] && [ "$MAINPID" != "0" ]; then
  PSTART=$(ps -o lstart= -p "$MAINPID" 2>/dev/null)
  PSTS=$(date -d "$PSTART" +%s 2>/dev/null || echo 0)
  CUTOFF=$(date -d 'today 07:50' +%s)
  HEALTH=$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 http://127.0.0.1:18789/health 2>/dev/null)
  if [ "$PSTS" -ge "$CUTOFF" ] && [ "$HEALTH" = "200" ] && [ "${RW_FORCE:-0}" != "1" ]; then
    say "今早已升级/重启（PID $MAINPID 起于 $PSTART，health=$HEALTH）→ 跳过重启（去重）"
    notify "【重启窗口】今早 08:00 后已完成升级重启，本窗口跳过，不再重复重启"
    exit 0
  fi
fi

# 1) 重启前自检
say "→ 重启前自检"
SC_RC=0
SC=$(timeout 240 bash "$W/tools/console-cmd.sh" selfcheck 2>&1) || SC_RC=$?
echo "$SC" > "$W/state/work/pre-restart-selfcheck.txt"
VERDICT=$(printf '%s\n' "$SC" | grep -oE 'PASS [0-9]+ / WARN [0-9]+ / FAIL [0-9]+' | tail -1)
PASSN=$(printf '%s' "$VERDICT" | sed -n 's/.*PASS \([0-9]\{1,\}\) .*/\1/p')
FAILN=$(printf '%s' "$VERDICT" | sed -n 's/.*FAIL \([0-9]\{1,\}\)$/\1/p')
WARNL=$(printf '%s\n' "$SC" | grep -E '^⚠️' | head -4)
say "自检结论：${VERDICT:-未取到} rc=$SC_RC"

# 失败关闭：任何"读不到/解析不出/自检自身失败"都不许继续（评审 VETO 修正 1）
if [ "$SC_RC" -ne 0 ] || [ -z "$VERDICT" ] || [ -z "$PASSN" ] || [ -z "$FAILN" ]; then
  say "自检结果不可信（rc=$SC_RC 结论='${VERDICT:-空}'）→ 取消重启"
  notify "【重启窗口】自检结果不可信（空输出/格式变化/命令失败），已按失败关闭取消重启。详见 state/work/pre-restart-selfcheck.txt"
  exit 5
fi
if [ "$PASSN" -lt 10 ]; then
  say "自检通过项仅 $PASSN 项（<10）→ 结果不可信，取消重启"
  notify "【重启窗口】自检通过项异常（$PASSN 项），取消重启"
  exit 5
fi

if [ "$FAILN" -gt 0 ]; then
  say "自检有 $FAILN 项 FAIL，取消本次重启"
  notify "【重启窗口】自检未通过（$VERDICT），已取消重启。原因见 state/work/pre-restart-selfcheck.txt"
  exit 6
fi

# 2026-10-31 双审必改项：模型链体检（悬空引用即取消；不可查=显式告警后继续）
MCOUT=$(cd "$W" && timeout 60 python3 tools/modelchain-check.py 2>&1); MCRC=$?
say "模型链体检 rc=$MCRC"
# 2026-11-17：瞬时探测抖动（B 机 ollama 睡眠/网络）重试 2 次，别一次失败就整天不重启
for _mtry in 1 2; do
  [ "$MCRC" -eq 0 ] && break
  sleep 15
  MCOUT=$(cd "$W" && timeout 60 python3 tools/modelchain-check.py 2>&1); MCRC=$?
  say "模型链体检重试$_mtry rc=$MCRC"
done
if [ "$MCRC" -eq 1 ]; then
  # 2026-11-17：只有 ollama/ 本地兜底模型悬空时降级为 WARN（本地模型是最后一档，坏了不该拦重启）
  NONOLLAMA=$(printf '%s\n' "$MCOUT" | grep -E '配置引用不存在|本地模型未安装|SUSPENDED' | grep -v 'ollama/' | head -3)
  if [ -z "$NONOLLAMA" ]; then
    say "模型链仅本地兜底引用异常（降级 WARN，不拦重启）"
    notify "【重启窗口】模型链仅本地兜底模型异常，按 WARN 继续：$(printf '%s' "$MCOUT" | grep -E 'ollama/' | head -2)"
  else
    notify "【重启窗口】模型链体检失败（云模型引用异常），已取消重启：$NONOLLAMA"
    exit 0
  fi
fi
if [ "$MCRC" -eq 2 ]; then
  notify "【重启窗口】模型链不可查（本地模型端不可达），按 WARN 继续并告警：$MCOUT"
fi

# 2) 备份新鲜度（午夜备份后重启最安全）
BA=$(ls -t /mnt/d/openclaw-backups/*openclaw-backup.tar.gz 2>/dev/null | head -1)
if [ -n "$BA" ]; then
  AGEH=$(( ( $(date +%s) - $(stat -c %Y "$BA") ) / 3600 ))
  say "最近备份：${AGEH}h 前"
  [ "$AGEH" -gt 30 ] && say "注意：备份偏旧（>30h），但仍按窗口执行"
fi

# 2.5) 升级已移到重启之后（2026-11-22 主公令）：见 5.6 升级链


# 3) 执行重启
if [ "$DRY" = "1" ]; then say "dry-run：不执行重启"; exit 0; fi
say "→ 提交受控重启"
NOTIFY_ACCOUNT=default notify "【即将重启】每日 08:00 受控重启开始，网关会有 1–2 分钟不可用。进度见果果助手面板顶部横幅，恢复后我会再报一条。"
touch "$W/state/work/.restart-in-progress"
python3 "$W/tools/activity.py" set kind=restart phase="网关重启中" percent=50 note="预计 1–2 分钟恢复" >/dev/null 2>&1 || true
OLD_PID=$(systemctl --user show -p MainPID --value openclaw-gateway 2>/dev/null)
bash "$W/tools/restart-gateway.sh" --reason "每日08:00窗口自动重启(自检通过 ${VERDICT})" 2>&1 | tail -4
RG_RC=${PIPESTATUS[0]}
say "重启提交 rc=$RG_RC"
if [ "$RG_RC" -ne 0 ]; then
  say "重启被拒绝或提交失败（rc=$RG_RC：备份静默窗/升级中/已有重启在跑），不视为故障"
  notify "【重启窗口】本次重启未执行（rc=$RG_RC），详见 state/work/restart-window.log"
  exit 8
fi

# 4) 重启后复检：必须等到「PID 换新 且 health 200」，预算 300s（评审修正）
H=000
for i in $(seq 1 30); do
  sleep 10
  H=$(timeout 6 curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/health 2>/dev/null || echo 000)
  NEW_PID=$(systemctl --user show -p MainPID --value openclaw-gateway 2>/dev/null)
  if [ "$H" = "200" ] && [ -n "$NEW_PID" ] && [ "$NEW_PID" != "0" ] && [ "$NEW_PID" != "$OLD_PID" ]; then break; fi
done
say "重启后健康：$H  PID: $OLD_PID → $NEW_PID"
# 评审 VETO 修正 2：不采信"已提交"，必须核验进程真的换新且健康 200
if [ "$H" != "200" ] || [ "$NEW_PID" = "$OLD_PID" ] || [ -z "$NEW_PID" ] || [ "$NEW_PID" = "0" ]; then
  say "重启未真正生效（健康=$H 旧=$OLD_PID 新=$NEW_PID）→ 交看门狗/自救，并告警"
  notify "【重启窗口】重启未生效：健康=$H，PID $OLD_PID→$NEW_PID。看门狗与自救已介入，请查看 state/work/restart-window.log"
  exit 7
fi
# 2026-11-25 修：原写法 tail -2|head -1 会抓到分隔线，导致升级闸门误判「体检未通过」
POST=$(timeout 240 bash "$W/tools/console-cmd.sh" selfcheck 2>&1 | grep -oE 'PASS [0-9]+ / WARN [0-9]+ / FAIL [0-9]+' | tail -1)
[ -z "$POST" ] && POST="PASS - / WARN - / FAIL -"
say "重启后自检：$POST"

# 5.6) 重启后升级链（2026-11-22 主公令：先重启 → 验备份 → 体检 → 升级）
if [ "$H" = "200" ]; then
  # 2026-11-24 主公令：仅工作日升级；周末只重启，不升级
  if [ "$(date +%u)" -ge 6 ]; then
    say "周末：按主公令不升级，只重启"
  else
  say "→ 升级链：验备份完整性"
  if ! timeout 300 bash "$W/tools/backup-integrity.sh" >> "$LOG" 2>&1; then
    say "备份完整性未通过 → 今日不升级"
    notify "【升级跳过】备份完整性未通过，今天只重启不升级。详见 state/work/backup-integrity.log"
  else
    DEC=$(timeout 180 python3 "$W/tools/upgrade-decide.py" 2>&1 | head -1)
    say "$DEC"
    case "$DEC" in
      *arm*)
        case "$POST" in
          *"FAIL 0"*)
            TGTUP=$(head -1 "$W/state/work/.upgrade-armed" 2>/dev/null | tr -d "[:space:]")
            say "体检通过（$POST）→ 升级到 $TGTUP"
            notify "【升级开始】$DEC；体检通过，开始安装并验证"
            if timeout 2400 bash "$W/tools/upgrade-panel.sh" --target "$TGTUP" >> "$LOG" 2>&1; then
              say "升级完成 rc=0"
              notify "【升级完成】已升级到 $TGTUP，13 项自检通过"
            else
              say "升级失败（按技能自动回滚）"
              notify "【升级失败】$TGTUP 安装未通过验收，已自动回滚，详见 state/work/upgrade-panel.log"
            fi
            rm -f "$W/state/work/.upgrade-armed" "$W/state/work/.upgrade-approved" ;;
          *) say "体检未通过（$POST）→ 不升级"
             notify "【升级拦截】重启后体检未通过（$POST），今天不升级" ;;
        esac ;;
      *) say "无需升级：$DEC" ;;
    esac
  fi
  fi
fi

# 5) 处理重启队列
if [ -f "$Q" ]; then
  N=$(grep -c '^- \[ \]' "$Q" 2>/dev/null || echo 0)
  say "重启队列待办：$N 项（详见 $Q）"
fi

# 5.5) 恢复/失败通知 + 清状态
if [ "$H" = "200" ]; then
  NOTIFY_ACCOUNT=default notify "【已恢复】网关已重新上线（health 200），服务正常，可以正常用了。"
else
  NOTIFY_ACCOUNT=default notify "【重启后异常】网关 health=$H，看门狗与自救已介入。"
fi
python3 "$W/tools/activity.py" clear >/dev/null 2>&1 || true
rm -f "$W/state/work/.restart-in-progress"

# 6) 报备
if [ "$H" = "200" ]; then
  notify "【重启窗口】已完成。自检 ${VERDICT}；重启后健康 $H；$POST
${WARNL:-}"
else
  notify "【重启窗口】重启后健康异常($H)，看门狗与自救已介入，请查看 state/work/restart-window.log"
fi
say "===== 重启窗口结束 ====="
