#!/bin/bash
# upgrade-acceptance.sh —— 升级后验收清单（12 项，只读；退出码 0 = 全绿）
set -uo pipefail
W=/home/j/.openclaw/workspace
P=0; F=0; FAILS=""
ok(){ printf "PASS  %-28s %s\n" "$1" "${2:-}"; P=$((P+1)); }
ng(){ printf "FAIL  %-28s %s\n" "$1" "${2:-}"; F=$((F+1)); FAILS="$FAILS $1"; }
chk(){ [ "$2" = "$3" ] && ok "$1" "$2" || ng "$1" "got=$2 want=$3"; }

# 1 网关在线
systemctl --user is-active openclaw-gateway >/dev/null && ok "gateway-active" || ng "gateway-active"
# 2 端口
ss -tln 2>/dev/null | grep -q ':18789' && ok "port-18789" || ng "port-18789"
# 3 版本
VER=$(timeout 20 openclaw --version 2>/dev/null | grep -oE '2026\.[0-9.]+' | head -1)
[ -n "${EXPECT_VER:-}" ] && chk "version" "$VER" "$EXPECT_VER" || ok "version" "${VER:-unknown}"
# 4 插件数（基线 53 启用）
EN=$(timeout 60 openclaw plugins list 2>/dev/null | grep -c "enabled" || echo 0)
[ "$EN" -ge 45 ] && ok "plugins-enabled" "$EN" || ng "plugins-enabled" "$EN<45"
# 5 autonomous.mode
AM=$(timeout 20 openclaw config get skills.workshop.autonomous.mode 2>/dev/null | tr -d '"' | tail -1)
chk "autonomous-mode" "${AM:-?}" "propose"
# 6 工作区全部解析一致
BAD=$(python3 -c "
import json,os
d=json.load(open('/home/j/.openclaw/openclaw.json'))
print(sum(1 for k,v in d['agents']['entries'].items() if v.get('workspace') and os.path.realpath(v['workspace'])!=v['workspace']))" 2>/dev/null || echo 999)
chk "workspaces-resolve" "${BAD:-999}" "0"
# 7 工作区目录存在
MISS=$(python3 -c "
import json,os
d=json.load(open('/home/j/.openclaw/openclaw.json'))
print(sum(1 for k,v in d['agents']['entries'].items() if v.get('workspace') and not os.path.isdir(v['workspace'])))" 2>/dev/null || echo 999)
chk "workspaces-exist" "${MISS:-999}" "0"
# 8 定时任务数
CJ=$(timeout 90 openclaw cron list --json 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print(len(d.get('jobs',d) if isinstance(d,dict) else d))" 2>/dev/null || echo 0)
[ "${CJ:-0}" -ge 80 ] && ok "cron-jobs" "$CJ" || ng "cron-jobs" "$CJ<80"
# 9 最新备份时效（<30h）
NEW=$(ls -t /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | head -1)
if [ -n "$NEW" ]; then AGE=$(( ( $(date +%s) - $(stat -c %Y "$NEW") ) / 3600 )); [ "$AGE" -lt 30 ] && ok "backup-age-h" "${AGE}h" || ng "backup-age-h" "${AGE}h"; else ng "backup-age-h" "none"; fi
# 10 配置校验
timeout 40 openclaw config validate >/dev/null 2>&1 && ok "config-valid" || ng "config-valid"
# 11 内存低于软线
MEM=$(systemctl --user show openclaw-gateway -p MemoryCurrent --value 2>/dev/null)
MB=$(( ${MEM:-0} / 1024 / 1024 )); [ "$MB" -lt 8000 ] && ok "gateway-mem-MB" "${MB}" || ng "gateway-mem-MB" "${MB}>=8000"
# 12 doctor 无失败（慢，可选）
if [ "${SKIP_DOCTOR:-0}" = 1 ]; then ok "doctor" "skipped"; else
  timeout 600 openclaw doctor > "$W/state/tmp/acc-doctor.txt" 2>&1; RC=$?
  [ "$RC" = 0 ] && ok "doctor" || ng "doctor" "rc=$RC"
fi

echo "-----"
echo "RESULT pass=$P fail=$F${FAILS:+ fails:$FAILS}"
[ "$F" = 0 ]
