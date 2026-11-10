#!/usr/bin/env bash
# 定时任务排期体检：同刻冲突 / 静默窗口 / 高峰时段
set -eo pipefail
TMP=$(mktemp)
openclaw automations list --all --json > "$TMP" 2>/dev/null
python3 - "$TMP" <<'PY'
import json,sys,collections
d=json.load(open(sys.argv[1]))
jobs=[j for j in d.get('jobs',[]) if j.get('enabled',True)]
by=collections.defaultdict(list); quiet=[]; peak=[]
for j in jobs:
    s=j.get('schedule') or {}
    if s.get('kind')!='cron': continue
    e=(s.get('expr') or ''); p=e.split()
    if len(p)<5: by['*'+e].append(j.get('name')); continue
    try: hh=int(p[1]); mi=int(p[0])
    except Exception: continue
    if p[0].isdigit():
        by['%02d:%02d'%(hh,mi)].append(j.get('name')); 
        if 4<=hh<6: quiet.append(j.get('name'))
        # 模型档位切换/播报属轻活且必须卡时段起点，不计入高峰违规
        light='model-slot.sh' in json.dumps(j.get('payload') or {})
        if (9<=hh<12 or 14<=hh<18) and not light: peak.append('%02d:%02d %s'%(hh,mi,j.get('name')))
    else:
        by['~'+e].append(j.get('name'))
print('== 同刻冲突（同一分钟多个任务）==')
conf=[t for t in sorted(by) if len(by[t])>=2]
for t in conf: print('  %s x%d  %s' % (t, len(by[t]), ' / '.join(by[t])))
if not conf: print('  无 ✅')
print('== 04:00-06:00 静默窗口（断网，应避免）==')
print('  无 ✅' if not quiet else '\n'.join('  '+x for x in quiet))
print('== 高峰时段 周一-五 09-12/14-18（重活应避开）==')
print('  无 ✅' if not peak else '\n'.join('  '+x for x in peak))
print('（共 %d 个启用任务）' % len(jobs))
PY
_rc=$?
if [ "$_rc" -ne 0 ]; then
  echo "⚠️ python 段失败(rc=$_rc)，保留临时文件供排查：$TMP" >&2
else
  rm -f "$TMP"
fi
exit "$_rc"
