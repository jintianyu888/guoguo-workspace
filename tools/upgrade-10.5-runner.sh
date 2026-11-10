#!/bin/bash
# upgrade-10.5-runner.sh v3 —— 网关外执行，三份评审（v4-pro/glm-5.3/kimi-k3）必改项已合并
# 关键时序（依据 C1 + B-M1/R1/R5）：
#   停网关释放 DB 租约 → doctor --fix 迁移（独占库）→ 起回网关 → 干净态整档备份+校验+三盘镜像
#   → dry-run → update --no-restart（拆开交接）→ 重启 → 失败整档回滚（DB+配置+二进制一起）
# 启动：systemd-run --user --unit=oc-upgrade-10.5 --collect /home/j/.openclaw/workspace/tools/upgrade-10.5-runner.sh
set -uo pipefail
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/upgrade-10.5-runner.log
mkdir -p "$WS/state/work"
exec >>"$LOG" 2>&1
ts(){ date '+%F %T'; }
say(){ echo "[$(ts)] $*"; }
notify(){ ( bash "$WS/tools/notify.sh" "$1" >/dev/null 2>&1 ) || say "notify 未送达: $1"; }
ROLLBACK=0
say "########## RUNNER v3 START $(ts) ##########"

# ---------- 0. 闸门 ----------
# 主公令 2026-10-22 19:56：加密补跑让路，升级优先；云端层以「主公豁免」凭据替代验证
if [ -f "$WS/state/work/cloud-waived.ok" ]; then
  AGE=$(( $(date +%s) - $(date -r "$WS/state/work/cloud-waived.ok" +%s) ))
  [ "$AGE" -gt 43200 ] && { say "GATE-FAIL1 豁免凭据超过 12h"; ABORT=1; }
  say "云端闸门：主公豁免（${AGE}s 前签发）"
elif [ -f "$WS/state/work/cloud-verified.ok" ]; then
  AGE=$(( $(date +%s) - $(date -r "$WS/state/work/cloud-verified.ok" +%s) ))
  [ "$AGE" -gt 7200 ] && { say "GATE-FAIL1b 云端凭据过期 ${AGE}s"; ABORT=1; }
else
  say "GATE-FAIL1 既无云端验证也无主公豁免"; ABORT=1
fi
UST=$(timeout 180 openclaw update status 2>&1)
echo "$UST" | grep -qi 'lancedb.*unfinished' && { say "GATE-FAIL2 memory-lancedb 未收口（应在 STAGE2 前已由 doctor 处理）"; }
[ "$(systemctl --user is-active openclaw-gateway)" = "active" ] || { say "GATE-FAIL3 网关未运行"; ABORT=1; }
NOWM=$((10#$(date +%H) * 60 + 10#$(date +%M)))
{ [ "$NOWM" -ge 30 ] && [ "$NOWM" -le 360 ]; } && { say "GATE-FAIL4 落在 00:30-06:00 禁窗"; ABORT=1; }
[ "${ABORT:-0}" = 0 ] || { say "ABORT 闸门未过，未做任何变更"; notify "⛔ 升级闸门未过，已中止（系统未变更）"; exit 10; }
say "闸门全绿"
say "公告缓冲 45s（让飞书把停机通知送达再停网关）"
sleep 45

# ---------- 1. 轻量兜底快照（doctor 前的最后一道） ----------
cp -f /home/j/.openclaw/openclaw.json "$WS/state/work/openclaw.json.pre-10.5" && say "config 快照已存"
tar czf /mnt/d/state-openclaw-pre-10.5.tgz -C /home/j --exclude='.openclaw/workspace/state/work/upgrade-10.5-runner.log' .openclaw/state 2>/dev/null && say "state 快照已存 /mnt/d"

# ---------- 2. 停网关 → doctor --fix（独占 agent-main 库，B-M1/R1） ----------
say "--- STAGE2 stop gateway + doctor --fix ---"
systemctl --user stop openclaw-gateway
for i in $(seq 1 40); do pgrep -f "openclaw.*gateway --port" >/dev/null || break; sleep 1; done
if pgrep -f "openclaw.*gateway --port" >/dev/null; then systemctl --user start openclaw-gateway; say "网关停不净 → 中止"; notify "⚠️ 网关停不干净，升级中止（未变更）"; exit 11; fi
# --force：确认工作区别名改指（/home/j/openclaw-workspaces/health-* → 云端备份区真实目录），
# 否则 doctor 会以 WorkspaceAliasRepointedError 拒绝，并连带卡死 node-host/rescue-pending/skill-workshop 三个迁移
timeout 1800 openclaw doctor --fix --force > "$WS/state/work/doctor-fix.txt" 2>&1 || { say "doctor --fix --force 非零退出"; DOCTOR_BAD=1; }
timeout 900 openclaw doctor > "$WS/state/work/doctor-pre-update.txt" 2>&1
N=$(grep -ci 'step-threw\|step-refused' "$WS/state/work/doctor-pre-update.txt" || true)
say "doctor 复查 step-threw/refused=$N"
[ "${N:-0}" -gt 0 ] && DOCTOR_BAD=1
UST2=$(timeout 180 openclaw update status 2>&1)
echo "$UST2" | grep -qi 'lancedb.*unfinished' && { say "lancedb 仍未收口"; DOCTOR_BAD=1; }
echo "$UST2" | grep -qi 'update failed' && say "WARN 10-20 失败残留仍在（记录在案，交 update 覆盖）"
systemctl --user start openclaw-gateway
for i in $(seq 1 45); do systemctl --user is-active openclaw-gateway | grep -q active && break; sleep 2; done
say "网关已恢复，doctor_bad=${DOCTOR_BAD:-0}"

# ---------- 3. 干净态整档备份 + 校验 + 三盘镜像（M3/M4/R2） ----------
say "--- STAGE3 pre-upgrade archive ---"
PRE=$(ls -t /mnt/d/openclaw-backups/*pre-upgrade*.tar.gz 2>/dev/null | head -1)
if [ "${SKIP_BACKUP:-0}" = 1 ] && [ -n "${PRE:-}" ]; then
  say "复用 2 小时内已生成的 pre-upgrade 归档（SKIP_BACKUP=1）：$PRE"
else
  timeout 3000 sh "$WS/tools/pre-upgrade-backup.sh" "升级 2026.10.4->2026.10.5" || { say "pre-upgrade 备份失败"; notify "⛔ 升级前备份失败，中止"; exit 12; }
  PRE=$(ls -t /mnt/d/openclaw-backups/*pre-upgrade*.tar.gz 2>/dev/null | head -1)
fi
[ -n "${PRE:-}" ] || { say "找不到新归档"; notify "⛔ 找不到新归档，中止"; exit 13; }
say "第一回滚源=$PRE"
timeout 1800 openclaw backup verify --archive "$PRE" >>"$LOG" 2>&1 || { say "新档校验失败"; notify "⛔ 新归档校验不过，中止"; exit 14; }
timeout 3600 sh "$WS/tools/align-backup-triple.sh" >>"$LOG" 2>&1 || say "WARN 三盘镜像失败（回滚仅 D）"

# ---------- 4. 进度闸门：doctor 出问题则在此止步 ----------
[ "${DOCTOR_BAD:-0}" = 0 ] || { say "doctor 未通过 → 不升级（备份已留，系统仍 10.4）"; notify "⛔ doctor 未过，未升级；已留新档 $PRE"; exit 15; }

# ---------- 5. dry-run + 升级（拆开交接 C2） ----------
say "--- STAGE5 dry-run ---"
timeout 600 openclaw update --dry-run >>"$LOG" 2>&1 || { say "dry-run 失败 → 不升级"; notify "⛔ dry-run 失败，未升级"; exit 16; }
say "--- STAGE5b update --yes --no-restart ---"
timeout 1800 openclaw update --yes --no-restart --timeout 600 || ROLLBACK=1

# ---------- 6. 重启并观察（C2） ----------
say "--- STAGE6 restart ---"
if [ "$ROLLBACK" = 0 ]; then
  systemctl --user restart openclaw-gateway
  for i in $(seq 1 60); do systemctl --user is-active openclaw-gateway | grep -q active && break; sleep 2; done
  systemctl --user is-active openclaw-gateway | grep -q active || ROLLBACK=1
  journalctl --user -u openclaw-gateway --since "3 min ago" 2>/dev/null | grep -iE "error|throw|Traceback" | tail -20 >>"$LOG"
fi

# ---------- 7. 整档回滚（R1/R5：DB+配置+二进制一起） ----------
if [ "$ROLLBACK" = 1 ]; then
  say "--- STAGE7 ROLLBACK ---"
  notify "⚠️ 升级失败，自动整档回滚中"
  systemctl --user stop openclaw-gateway
  npm install -g openclaw@2026.10.4 >>"$LOG" 2>&1 || say "二进制降级失败，需人工"
  openclaw backup restore --archive "$PRE" >>"$LOG" 2>&1 || say "整档恢复失败，需人工（源=$PRE）"
  [ "$NOWM" -ge 0 ] && [ "$NOWM" -le 60 ] && say "R4 提醒：已过 00:00，当晚 01:00 备份需跳过一次"
  systemctl --user start openclaw-gateway; sleep 25
fi

# ---------- 8. 验收（三份评审补漏项） ----------
say "--- STAGE8 verify ---"
say "version=$(timeout 60 openclaw --version 2>&1 | head -1)"
say "plugins=$(timeout 120 openclaw plugins list 2>/dev/null | head -1)"
say "autonomous.mode=$(python3 -c "import json;print(json.load(open('/home/j/.openclaw/openclaw.json')).get('skills',{}).get('workshop',{}).get('autonomous',{}).get('mode'))" 2>/dev/null)"
say "imap.enabled=$(python3 -c "import json;print(json.load(open('/home/j/.openclaw/openclaw.json')).get('plugins',{}).get('entries',{}).get('imap',{}).get('enabled'))" 2>/dev/null)"
say "unit_mem=$(systemctl --user show openclaw-gateway -p MemoryHigh -p MemoryMax | tr '\n' ' ')"
say "unit_unrecognized=$(systemctl --user cat openclaw-gateway.service 2>&1 | grep -ci unrecognized || true)"
say "gw_pid=$(pgrep -f 'openclaw.*gateway --port' | head -1)"
say "worktree_files=$(find "$WS" -type f 2>/dev/null | wc -l)"
UST3=$(timeout 180 openclaw update status 2>&1)
echo "$UST3" | grep -qi 'update failed' && say "VERIFY-WARN update 状态机仍记 failed"
echo "$UST3" >> "$WS/state/work/update-status-post.txt"
say "########## RUNNER v3 DONE rollback=$ROLLBACK $(ts) ##########"
notify "升级收尾：$(timeout 60 openclaw --version 2>&1 | head -1) · rollback=$ROLLBACK · 日志 state/work/upgrade-10.5-runner.log"
exit $([ "$ROLLBACK" = 0 ] && echo 0 || echo 20)
