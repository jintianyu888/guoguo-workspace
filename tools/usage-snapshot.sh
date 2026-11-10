#!/usr/bin/env bash
# usage-snapshot.sh v2 —— 每日用量快照（P2 2026-10-26：flock + 按日 JSON + 日对比 + 失败 exit 3）
# 产出：state/usage/YYYY-MM-DD.json（当日一份）+ state/agent-usage-history.jsonl（历史追加）
# 用法: bash tools/usage-snapshot.sh [--quiet]
set -u
W=/home/j/.openclaw/workspace
OUT=$W/state/usage
H=$W/state/agent-usage-history.jsonl
LOCK=$W/state/work/.usage-snapshot.lock
LOG=$W/state/work/usage-snapshot.log
D=$(date +%F)
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
mkdir -p "$OUT" "$(dirname "$LOCK")"
log(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }
exec 9>"$LOCK"
if ! flock -n 9; then log "SKIP 已有实例在跑"; exit 0; fi

if ! N=$(python3 - "$OUT" "$H" "$D" <<'PYEOF'
import sqlite3, glob, os, subprocess, json, datetime, sys
W='/home/j/.openclaw'
out_dir, hist, day = sys.argv[1], sys.argv[2], sys.argv[3]
rows={}
for d in sorted(glob.glob(f'{W}/workspace*')):
    n=os.path.basename(d); name=n.replace('workspace-','') if n!='workspace' else 'main'
    try: kb=int(subprocess.run(['du','-sk',d],capture_output=True,text=True).stdout.split()[0])
    except Exception: kb=0
    ev=0
    try:
        p=f'{W}/agents/{name}/agent/openclaw-agent.sqlite'
        if os.path.exists(p):
            c=sqlite3.connect(p); ev=list(c.execute('select count(*) from transcript_events'))[0][0]; c.close()
    except Exception: pass
    rows[name]={'kb':kb,'events':ev}
now=datetime.datetime.now()
snap={'ts':now.isoformat(timespec='seconds'),'date':day,'agents':rows,
      'total_kb':sum(v['kb'] for v in rows.values()),'total_events':sum(v['events'] for v in rows.values())}
dst=os.path.join(out_dir,day+'.json')
json.dump(snap,open(dst,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
with open(hist,'a',encoding='utf-8') as f:
    f.write(json.dumps(snap,ensure_ascii=False)+'\n')
# 日对比：找上一个快照
prev=None
for fn in sorted(glob.glob(os.path.join(out_dir,'20*.json'))):
    if os.path.basename(fn)[:10] < day:
        try: prev=json.load(open(fn,encoding='utf-8'))
        except Exception: prev=None
if prev:
    dk=snap['total_kb']-prev.get('total_kb',0); de=snap['total_events']-prev.get('total_events',0)
    print(f"usage {day}: kb={snap['total_kb']} ({dk:+d} vs {prev.get('date')}) events={snap['total_events']} ({de:+d})")
else:
    print(f"usage {day}: kb={snap['total_kb']} events={snap['total_events']} (无上一份快照)")
print('agents: '+', '.join(f"{k}={v['kb']}KB/{v['events']}ev" for k,v in sorted(rows.items())))

PYEOF
); then
  log "FAIL python 采集失败"
  NOTIFY_ALERT=1 bash "$W/tools/notify.sh" --alert "用量快照失败：$D（详见 $LOG）" >/dev/null 2>&1 || true
  exit 3
fi
echo "$N" | head -1 >> "$LOG"
[ "${1:-}" = "--quiet" ] || echo "$N"
exit 0
