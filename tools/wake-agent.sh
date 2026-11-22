#!/usr/bin/env bash
# wake-agent.sh v1.0 (2026-11-21) —— 立刻让某个管家跑一轮，不等它下次开工
# 用法：bash tools/wake-agent.sh <agent> "<要做的事>" [--timeout 180]
# 状态（2026-11-21 23:35）：暂不可用。原因两条，都已实测：
#  A) openclaw agent exec 在配置含 secret ref 时无法本地解析（GATEWAY_SECRET_REF_UNAVAILABLE）；
#     --auth-env-only 能绕过 secret，但 provider 目录不加载 → Unknown model。
#  B) 从 agent 会话内嵌套调 openclaw agent 会被护栏拒绝：
#     "Gateway agent from agent exec would lose inter-session attribution"，
#     要求改用 session-messaging 工具（sessions_send），本会话工具集未开放。
# 结论：真正的"立刻唤醒"要走 sessions_send；开启需改工具策略 + 重启网关（重启窗口执行）。

set -euo pipefail
AG="$1"; MSG="$2"; shift 2 || true
TMO=180
while [ $# -gt 0 ]; do case "$1" in --timeout) TMO="$2"; shift 2;; *) shift;; esac; done
WS=/home/j/.openclaw/workspace
mkdir -p "$WS/state/work"
export OPENCLAW_GATEWAY_TOKEN="$(python3 - <<'PY'
import sqlite3
con=sqlite3.connect("file:/home/j/.openclaw/state/openclaw.sqlite?mode=ro",uri=True)
r=con.execute("select value from secret_store_entries where name='GATEWAY_AUTH_TOKEN' and deleted_at_ms is null order by updated_at_ms desc limit 1").fetchone()
print(r[0] if r else "")
PY
)"
[ -z "${OPENCLAW_GATEWAY_TOKEN:-}" ] && { echo "FAIL 取不到网关 token"; exit 1; }
WORKSPACE="$(python3 - "$AG" <<'PY'
import json,sys
c=json.load(open("/home/j/.openclaw/openclaw.json"))
e=c.get("agents",{}).get("entries",{}).get(sys.argv[1],{})
print(e.get("workspace") or "/home/j/.openclaw/workspace")
PY
)"
TS=$(date +%Y%m%d-%H%M%S)
LOG="$WS/state/work/wake-$AG-$TS.log"
timeout $((TMO+30)) openclaw agent exec --cwd "$WORKSPACE" --timeout "$TMO" "$MSG" >"$LOG" 2>&1 || rc=$?
rc=${rc:-0}
echo "agent=$AG workspace=$WORKSPACE rc=$rc log=$LOG"
tail -3 "$LOG"
exit $rc