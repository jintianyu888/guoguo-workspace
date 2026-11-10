#!/bin/bash
# post-upgrade-check.sh —— 升级后兼容自检（2026-11-09 立）
# 目的：升级不只看 health，还要确认配置可解析、插件全在、cron/agent 数量没丢、模型链没断。
# 用法：bash tools/post-upgrade-check.sh [--quiet]
set -u
OCBIN=$(command -v openclaw 2>/dev/null || true)
[ -x "$OCBIN" ] || OCBIN=/home/j/.npm-global/bin/openclaw
W=/home/j/.openclaw/workspace
TS=$(date +%Y%m%d-%H%M%S)
OUT="$W/state/work/post-upgrade-$TS.md"
QUIET=0; [ "${1:-}" = "--quiet" ] && QUIET=1
FAIL=0; WARN=0
line(){ printf '%s\n' "$*" >>"$OUT"; }
ok(){ line "- ✅ $*"; }
bad(){ line "- ❌ $*"; FAIL=$((FAIL+1)); }
warn(){ line "- ⚠️ $*"; WARN=$((WARN+1)); }

VER=$("$OCBIN" --version 2>/dev/null | awk '{print $2}')
line "# 升级后兼容自检 $TS"
line ""
line "版本：${VER:-未知}"
line ""

# 1 配置
if "$OCBIN" config validate >/tmp/puc-config.$$ 2>&1; then ok "配置可解析"; else bad "配置校验失败：$(tail -2 /tmp/puc-config.$$ | tr '\n' ' ')"; fi

# 2 插件
PLUG=$("$OCBIN" plugins list --json 2>/dev/null)
if [ -n "$PLUG" ]; then
  PC=$(printf '%s' "$PLUG" | python3 -c 'import sys,json;d=json.load(sys.stdin);ps=d.get("plugins",d) if isinstance(d,(dict,list)) else [];print(len(ps))' 2>/dev/null || echo '?')
  if [ "$PC" = "?" ] || [ "$PC" = "0" ]; then warn "插件数量取不到或为 0"; else ok "插件 $PC 个已加载"; fi
else
  warn "插件清单取不到"
fi

# 3 cron
CJ=$("$OCBIN" cron list --json 2>/dev/null)
if [ -n "$CJ" ]; then
  read -r TOT ENB <<EOF
$(printf '%s' "$CJ" | python3 -c 'import sys,json;d=json.load(sys.stdin);j=d.get("jobs",d);j=[x for x in j if isinstance(x,dict)];print(len(j), sum(1 for x in j if x.get("enabled")))' 2>/dev/null || echo "? ?")
EOF
  if [ "$TOT" = "?" ]; then warn "cron 数量取不到"
  elif [ "$ENB" -lt 90 ]; then bad "启用中的任务仅 $ENB/$TOT（预期 ≥90）"
  else ok "定时任务 $ENB/$TOT 启用"; fi
else
  warn "cron 清单取不到"
fi

# 4 agents
AG=$("$OCBIN" agents list --json 2>/dev/null | python3 -c 'import sys,json;d=json.load(sys.stdin);a=d.get("agents") if isinstance(d,dict) else d;print(len(a))' 2>/dev/null || echo '?')
case "$AG" in ''|'?') warn "agent 数量取不到";; *) [ "$AG" -lt 30 ] && bad "agent 只有 $AG 个（预期 ≥30）" || ok "agent $AG 个";; esac

# 5 网关
H=$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 http://127.0.0.1:18789/health 2>/dev/null); [ -n "$H" ] || H=000
[ "$H" = "200" ] && ok "网关 health 200" || bad "网关 health=$H"

# 6 模型链
if python3 "$W/tools/modelchain-check.py" >/tmp/puc-mc.$$ 2>&1; then ok "模型链 OK"; else bad "模型链异常：$(tail -1 /tmp/puc-mc.$$ | cut -c1-120)"; fi

# 7 面板
PH=$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 http://127.0.0.1:8899/ 2>/dev/null); [ -n "$PH" ] || PH=000
[ "$PH" = "200" ] && ok "面板 200" || warn "面板 health=$PH"

line ""
if [ "$FAIL" -gt 0 ]; then line "**结论：FAIL（$FAIL 项失败 / $WARN 项存疑）**"; else line "**结论：PASS（0 失败 / $WARN 项存疑）**"; fi
rm -f /tmp/puc-config.$$ /tmp/puc-mc.$$
SUMMARY="升级自检 ${VER:-?}：$([ "$FAIL" -gt 0 ] && echo "FAIL $FAIL 项" || echo "PASS")（$OUT）"
[ "$QUIET" = "0" ] && echo "$SUMMARY"
[ "$FAIL" -gt 0 ] && [ "$QUIET" = "0" ] && NOTIFY_FROM=main NOTIFY_BELONG=升级 bash "$W/tools/notify.sh" --alert "❌ $SUMMARY" >/dev/null 2>&1
exit $([ "$FAIL" -gt 0 ] && echo 1 || echo 0)
