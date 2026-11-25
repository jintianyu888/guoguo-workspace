#!/bin/bash
# r41-selfcheck-parse.sh —— 防止「解析人类可读输出用 tail/head 定位行号」回归
# 2026-11-25 立：restart-window.sh 曾用 tail -2|head -1 取体检结论，抓到分隔线→升级整天被跳过
set -uo pipefail
W=/home/j/.openclaw/workspace
F=${R41_FILE:-$W/tools/restart-window.sh}
bad=0
# 1) restart-window.sh 里 selfcheck 的结果必须走正则解析
if grep -qE 'console-cmd\.sh"? selfcheck[^|]*\| *tail -2 *\| *head -1' "$F" 2>/dev/null; then
  echo "FAIL restart-window.sh 又用 tail -2|head -1 取体检结论（应改用正则抓 PASS/WARN/FAIL）"; bad=1
fi
if ! grep -q "grep -oE 'PASS \[0-9\]+ / WARN \[0-9\]+ / FAIL \[0-9\]+'" "$F" 2>/dev/null; then
  echo "FAIL restart-window.sh 缺少 PASS/WARN/FAIL 正则解析（可能被改回旧写法）"; bad=1
fi
# 2) 空值兜底必须存在
grep -q 'POST="PASS - / WARN - / FAIL -"' "$F" 2>/dev/null || { echo "FAIL restart-window.sh 缺少解析失败时的空值兜底"; bad=1; }
# 3) 升级闸门的回滚判定不得依赖兼容自检（探针竞态会假 FAIL）
if grep -q 'POST.*FAIL 0' "$F" 2>/dev/null && ! grep -qE 'ROLLBACK=1' "$F" 2>/dev/null; then
  echo "WARN 升级闸门未置 ROLLBACK 标记（确认回滚由 upgrade-panel 承担）"
fi
if [ "$bad" = "0" ]; then echo "GREEN 自检解析与回滚判定符合要求（R41）"; exit 0; fi
echo "修复：$F 中 selfcheck 结果改 grep -oE 'PASS n / WARN n / FAIL n' | tail -1，保留空值兜底"
exit 1
