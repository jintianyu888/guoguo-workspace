#!/bin/bash
[ -z "${BASH_VERSION:-}" ] && exec /bin/bash "$0" "$@"
# window-a.sh —— 一个维护窗口跑完：停网 → doctor --fix → update repair → 恢复
# 用法（在你的终端里）：bash ~/.openclaw/workspace/tools/window-a.sh
set -uo pipefail
W=/home/j/.openclaw/workspace
LOG=$W/state/work/window-a.log
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
trap 'say "异常退出，尝试恢复网关"; sh "$W/tools/maintenance.sh" stop' EXIT

say "=== WINDOW A START ==="
sh "$W/tools/maintenance.sh" start || { say "start 失败，中止"; exit 1; }

say "--- doctor --fix --force ---"
sh "$W/tools/maintenance.sh" run timeout 1500 openclaw doctor --fix --force > "$W/state/work/doctor-windowA.txt" 2>&1
say "doctor rc=$?"
echo "alias=$(grep -c WorkspaceAliasRepointed "$W/state/work/doctor-windowA.txt") threw=$(grep -c step-threw "$W/state/work/doctor-windowA.txt")" >> "$LOG"

say "--- update repair ---"
sh "$W/tools/maintenance.sh" run timeout 900 openclaw update repair > "$W/state/work/repair-windowA.txt" 2>&1
say "repair rc=$?"

say "--- 恢复网关 ---"
sh "$W/tools/maintenance.sh" stop
trap - EXIT

sleep 15
say "--- 验收 ---"
bash "$W/tools/upgrade-acceptance.sh" > "$W/state/work/acceptance-windowA.txt" 2>&1
tail -1 "$W/state/work/acceptance-windowA.txt" | tee -a "$LOG"
say "=== WINDOW A END ==="
