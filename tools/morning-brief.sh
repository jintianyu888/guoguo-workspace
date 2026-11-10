#!/usr/bin/env bash
# morning-brief.sh v2 —— 晨间简报（确定性，零 token）
# 2026-10-18 改造：任务区改为调用 tasks-footer.py --brief（唯一数据源 state/tasks/tasks.json），
# 已完成项不再重复播报；超过 14 天未更新的折叠为「陈旧待核实」只报计数。
WS=/home/j/.openclaw/workspace
# GLM 评审加固：渲染失败降级为纯计数，绝不让简报断掉
if ! python3 "$WS/tools/tasks-footer.py" --brief; then
  python3 - "$WS" <<'PYEOF'
import json,sys,os
WS=sys.argv[1]
try:
    d=json.load(open(os.path.join(WS,"state/tasks/tasks.json"),encoding="utf-8"))
    it=[x for x in d.get("items",[]) if x.get("status")=="open"]
    print("任务区渲染失败，降级计数：待办 %d 项" % len(it))
except Exception:
    print("任务区渲染失败且台账不可读")
PYEOF
fi
echo "---"
# 日程（今日～后天）
python3 - "$WS" <<'PYEOF'
import json,os,sys,datetime
WS=sys.argv[1]
today=datetime.date.today(); end=today+datetime.timedelta(days=2)
def load(p):
    try: return json.load(open(p,encoding="utf-8"))
    except Exception: return None
out=[]; sched=[]
for fn in ("state/schedule-hub.json","schedule-report.json"):
    d=load(os.path.join(WS,fn))
    if not d: continue
    for i in d.get("items",[]):
        dt=i.get("日期","")
        if not dt: continue
        try: dd=datetime.date.fromisoformat(dt)
        except Exception: continue
        if today<=dd<=end and i.get("状态","待办") in ("待办","open"):
            sched.append(i)
seen=set()
for i in sorted(sched,key=lambda x:(x.get("日期",""),x.get("时间",""))):
    k=(i.get("日期"),i.get("事项"))
    if k in seen: continue
    seen.add(k)
    s=((" "+i.get("时间")) if i.get("时间") else "")+i.get("事项","")
    out.append("- "+i.get("日期","")+" "+s)
if out:
    print("【日程】")
    print(chr(10).join(out))
else:
    print("今日暂无日程")
PYEOF
echo "---"
sh "$WS/tools/peak-status.sh" 2>/dev/null | head -3
