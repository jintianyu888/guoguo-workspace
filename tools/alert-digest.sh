#!/bin/bash
# alert-digest.sh —— 「信息维护 + 果果告警」统一摘要（只读，零 token）
# 用法: bash tools/alert-digest.sh [--hours N]  默认 8 小时窗口
# 输出：一段紧凑文本；无内容时输出「窗口内无告警」并 exit 0
set -uo pipefail
WS="/home/j/.openclaw/workspace"
HOURS=8
[ "${1:-}" = "--hours" ] && HOURS="${2:-8}"
SINCE_EPOCH=$(( $(date +%s) - HOURS*3600 ))
SINCE_STR=$(date -d "@$SINCE_EPOCH" "+%Y-%m-%d %H:%M")
printf "== 告警摘要 窗口: 近 %s 小时（自 %s）==\n" "$HOURS" "$SINCE_STR"

n=0
sec() { printf "\n---- %s ----\n" "$1"; }

# 1) 告警总线 state/alerts/alerts.jsonl（按 ts 过滤）
sec "告警总线 alerts.jsonl"
if [ -s "$WS/state/alerts/alerts.jsonl" ]; then
  python3 - "$WS/state/alerts/alerts.jsonl" "$SINCE_EPOCH" <<'PY' 2>/dev/null | tail -25
import json,sys,datetime
p,se=sys.argv[1],int(sys.argv[2])
out=[]
for line in open(p,encoding='utf-8',errors='replace'):
    line=line.strip()
    if not line: continue
    try: d=json.loads(line)
    except Exception: continue
    ts=d.get('ts') or d.get('at') or d.get('time') or ''
    ep=None
    if isinstance(ts,(int,float)): ep=int(ts/1000 if ts>1e11 else ts)
    elif isinstance(ts,str) and ts:
        for f in ("%Y-%m-%dT%H:%M:%S","%Y-%m-%d %H:%M:%S","%Y-%m-%dT%H:%M:%S.%f"):
            try: ep=int(datetime.datetime.strptime(ts[:26].replace('Z',''),f).timestamp()); break
            except Exception: pass
    if ep is None or ep<se: continue
    lvl=str(d.get('level') or d.get('severity') or '')[:8]
    src=str(d.get('source') or d.get('src') or d.get('name') or '')[:22]
    msg=str(d.get('message') or d.get('msg') or d.get('text') or '')[:150].replace('\n',' ')
    out.append(f"[{ts[:19]}] {lvl:8} {src:22} {msg}")
print("\n".join(out[-25:]) if out else "(窗口内无记录)")
PY
  n=$((n+1))
else
  echo "(文件不存在或为空)"
fi

# 2) NAS 挂载健康
sec "NAS 挂载健康"
if [ -f "$WS/state/nas-mount-health.log" ]; then
  awk -v s="$SINCE_STR" '$0>=s' "$WS/state/nas-mount-health.log" 2>/dev/null | grep -E 'ALERT|DOWN|RECOVERED|SKIP' | tail -10 || echo "(窗口内无异常)"
else echo "(无日志)"; fi

# 3) 会话哨兵
sec "会话哨兵 session-guard"
ls -1 "$WS/state/session-guard/"*.log 2>/dev/null | tail -2 | while read -r f; do
  grep -E 'P1|P2|P3|FAIL' "$f" 2>/dev/null | tail -5 | sed "s#^#$(basename "$f"): #"
done | tail -10 || true

# 4) 定时任务失败（真实真源：automations）
sec "定时任务 lastRunStatus=error"
timeout 40 openclaw automations list --json 2>/dev/null | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print('(读取失败)'); raise SystemExit
jobs=d.get('jobs',d if isinstance(d,list) else [])
bad=[j for j in jobs if j.get('lastRunStatus')=='error']
if not bad: print('(无失败任务)')
for j in bad[:12]:
    e=(j.get('lastRunError') or '').split('\n')[0][:110]
    print(f\"- {j.get('name')} | agent={j.get('effectiveAgentId')} | {e}\")
print(f'合计失败 {len(bad)} / 共 {len(jobs)}')
" 2>/dev/null

# 5) maint 启动通知失败计数
sec "maint boot-notice"
MB="/home/j/openclaw-workspaces/maint/state"
if [ -d "$MB" ]; then
  for f in boot-notice.fails boot-notice.success; do
    [ -f "$MB/$f" ] && printf "%s=%s " "$f" "$(cat "$MB/$f" 2>/dev/null | tr -d '\n')"
  done; echo
  [ -f "$MB/boot-notice.log" ] && tail -3 "$MB/boot-notice.log" | sed 's/^/  /'
else echo "(maint state 不可达)"; fi

# 6) 网关错误（去重前 12 条）
sec "网关 journal 错误"
timeout 20 journalctl --user -u openclaw-gateway --since "-${HOURS}h" --no-pager 2>/dev/null \
  | grep -iE '\[diagnostic\].*error=|Embedded agent failed|spawn failed|request handler failed|exec denied|database or disk is full|SqliteWorkerError|ERR_SQLITE_ERROR|slow SQLite|reclamation' \
  | sed -E 's/^.{0,20}[0-9]{4}-[0-9]{2}-[0-9]{2}T([0-9:]{8}).*error="?([^"]{0,110}).*/\1 \2/' \
  | sort -k2 | uniq -f1 -c | sort -rn | head -12 || echo "(读取失败)"

echo
echo "== 摘要结束 =="
exit 0
