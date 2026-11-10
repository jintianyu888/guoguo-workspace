#!/bin/bash
# morning-plan.sh v3 — 晨间计划汇报 + 自动执行闸门（2026-11-01 主公令）
# v3：owner 项=结构化标记(kind=decision/p0 或标题含待拍板)；其余入自动清单，含 P0 词的加警示标
set -uo pipefail
WS=/home/j/.openclaw/workspace
GATE=$WS/state/work/autorun-gate.json
DB=$WS/state/tasks/tasks.db
TODAY=$(date +%Y%m%d)
DRY=0
for a in "$@"; do case "$a" in --dry-run) DRY=1;; esac; done

declare -A CN=([maint]="维护管家" [backup]="备份管家" [model]="模型管家" [work]="干活管家")
declare -A WD=([maint]=/home/j/openclaw-workspaces/maint [backup]=/home/j/.openclaw/workspace-backup [model]=/home/j/.openclaw/workspace-model [work]=/home/j/openclaw-workspaces/work)
ORDER="maint backup model work"

echo "📋 晨间计划 · $(date "+%m-%d")"
echo ""
for s in $ORDER; do
  book=$(ls -1t "${WD[$s]}"/WORK-本周任务-*.md 2>/dev/null | head -1)
  echo "【${CN[$s]}】"
  if [ -z "$book" ]; then
    echo "  · 缺本周任务书"
    echo ""
    continue
  fi
  plan=$(sed -n '/本周五个具体任务/,/验收标准/p' "$book" | grep -E '^T[0-9]+[ 、.]' | sed -E 's/[*_]/ /g' | cut -c1-70 | head -6)
  if [ -z "$plan" ]; then
    echo "  · 任务书存在但未解析出条目"
  else
    echo "$plan" | sed "s/^/  · /"
  fi
  echo ""
done

echo "【要主公拍板】"
OWNER_TXT=$(python3 - "$DB" <<'PY'
import sqlite3,sys
c=sqlite3.connect('file:%s?mode=ro'%sys.argv[1],uri=True)
q="select no,title,coalesce(kind,'') from tasks where status not in ('done','cancelled','quarantine') order by no"
rows=[r for r in c.execute(q) if r[2] in ('decision','p0') or '待拍板' in (r[1] or '')]
print(len(rows))
for no,t,k in rows: print('  · #%s %s'%(no,t))
PY
)
OWNER_N=$(printf "%s\n" "$OWNER_TXT" | head -1)
printf "%s\n" "$OWNER_TXT" | tail -n +2
[ "$OWNER_N" = "0" ] && echo "  · 无 —— 今天没有需要你拍板的事"
echo ""

echo "【我将自动执行】"
AUTO_TXT=$(python3 - "$DB" <<'PY'
import sqlite3,sys
c=sqlite3.connect('file:%s?mode=ro'%sys.argv[1],uri=True)
q="select no,title,coalesce(agent,'main'),coalesce(kind,'') from tasks where status in ('open','in_progress','pending') order by no"
K=('升级','重启','关机','权限','密钥','防火墙','批量删除')
rows=[r for r in c.execute(q) if r[3] not in ('decision','p0') and '待拍板' not in (r[1] or '')]
print(len(rows))
for no,t,ag,k in rows:
    warn='  ⚠含P0词' if any(x in (t or '') for x in K) else ''
    print('  · #%s [%s] %s%s'%(no,ag,t,warn))
PY
)
AUTO_N=$(printf "%s\n" "$AUTO_TXT" | head -1)
printf "%s\n" "$AUTO_TXT" | tail -n +2 | head -12
[ "$AUTO_N" -gt 12 ] && echo "  … 另有 $((AUTO_N-12)) 项，见任务库"
[ "$AUTO_N" = "0" ] && echo "  · 无待办"
echo ""

if [ "$OWNER_N" -eq 0 ]; then
  DEC=GO
  echo "✅ 闸门：GO —— 无主公项，按计划开工；P0 事项仍停手报你。"
else
  DEC=WAIT
  echo "⏸ 闸门：WAIT —— 有 $OWNER_N 项等你拍板，管家只做常规巡检。"
fi
if [ "$DRY" -eq 0 ]; then
  printf '{"schema":1,"date":"%s","owner_items":%s,"auto_items":%s,"decision":"%s","ts":"%s"}\n' "$TODAY" "$OWNER_N" "$AUTO_N" "$DEC" "$(date -Iseconds)" > "$GATE.tmp" && mv -f "$GATE.tmp" "$GATE"
  echo ""
  echo "（闸门已写 $GATE）"
else
  echo ""
  echo "（dry-run：闸门未落盘）"
fi
