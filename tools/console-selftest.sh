#!/usr/bin/env bash
# 果果助手 自身试跑器 v1（2026-10-29）
# 目的：不开窗也能验证「每个按钮背后的命令」是否真能用。
# 只跑安全子集；重启/升级/即时备份只验证「安全闸门」是否拦得住，不真的执行。
set -u
WS=/home/j/.openclaw/workspace
CC="$WS/tools/console-cmd.sh"
PASS=0; FAIL=0; SKIP=0
ok(){ PASS=$((PASS+1)); printf '  ✅ %-22s %s\n' "$1" "$2"; }
no(){ FAIL=$((FAIL+1)); printf '  ❌ %-22s %s\n' "$1" "$2"; }
sk(){ SKIP=$((SKIP+1)); printf '  ⏭  %-22s %s\n' "$1" "$2"; }

chk(){ # 名称 命令 期望关键字
  local name=$1 cmd=$2 pat=$3 out rc
  out=$(timeout 150 bash -c "$cmd" 2>&1); rc=$?
  if [ $rc -ne 0 ]; then no "$name" "rc=$rc"; return; fi
  if [ -z "$pat" ] || printf '%s' "$out" | grep -qE "$pat"; then ok "$name" "$(printf '%s' "$out" | head -1 | cut -c1-40)"; else no "$name" "输出不含 $pat"; fi
}

echo "===== 果果助手 试跑 $(date '+%F %T') ====="
echo "[1] 只读/报告类按钮"
chk "状态总览"   "bash $CC status"      "网关 health"
chk "一键自检"   "bash $CC selfcheck"   "PASS [0-9]+ / WARN [0-9]+ / FAIL [0-9]+"
chk "服务清单"   "bash $CC services"    "openclaw-gateway"
chk "查看日志"   "bash $CC logs"        "网关最近日志"
chk "诊断包"     "bash $CC diag"        "已保存"
chk "备份状态"   "bash $CC backups"     "备份"
chk "额度与模型" "bash $CC quota"       "."
chk "今日简报"   "bash $CC brief"       "待办|拍板"
chk "清理预演"   "bash $CC clean-dry"   "."

echo "[2] 自动修复（网关健康时只报告，不重启）"
chk "自动修复"   "bash $CC fix"         "自检|修复|通过"

echo "[3] 安全闸门（只验证拦得住，不真执行）"
MARK="$WS/state/work/.upgrade-running"
if [ -e "$MARK" ]; then sk "重启闸门" "已存在 .upgrade-running，跳过（避免误判）"
else
  : > "$MARK"
  out=$(timeout 30 bash "$WS/tools/restart-gateway.sh" --reason "selftest-gate" 2>&1); rc=$?
  rm -f "$MARK"
  if [ $rc -ne 0 ] && printf '%s' "$out" | grep -qE "升级|忽略|拒绝|跳过"; then ok "重启闸门" "rc=$rc 被正确拦截"; else no "重启闸门" "rc=$rc 未拦截"; fi
fi
# 检查 fail-closed 升级自检闸门 (变量名: SCV) 是否在位；2026-11-05 23:25 起闸门迁到 tools/upgrade-openclaw.sh，两处合并计数
out=$(timeout 20 bash -c "cd $WS && cat tools/console-cmd.sh tools/upgrade-openclaw.sh 2>/dev/null | grep -c 'SCV'" 2>&1)
[ "${out:-0}" -ge 2 ] && ok "升级自检闸门" "代码在位（fail-closed）" || no "升级自检闸门" "闸门代码缺失"

echo "[4] 不试跑的（会真干活，需你点头）"
sk "重启网关"   "会真的重启，落到每天 09:00 窗口跑"
sk "一键升级"   "会真的升级；当前 $(timeout 15 bash $CC status 2>/dev/null | grep -o 'OpenClaw [0-9.]*' | head -1)"
sk "立即备份"   "会真跑 40G 全量，约 1 小时"

echo "------------------------------"
printf "结果：PASS %d / FAIL %d / SKIP %d\n" $PASS $FAIL $SKIP
[ $FAIL -eq 0 ] && echo "结论：果果助手后端可用" || echo "结论：有 FAIL，需要修"
exit $([ $FAIL -eq 0 ] && echo 0 || echo 1)
