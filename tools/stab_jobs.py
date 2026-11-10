import json,time
import os,sys
_p=(sys.argv[1] if len(sys.argv)>1 else "") or os.environ.get("STAB_JOBS") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"state/tmp/stab_jobs.json")
d=json.load(open(_p,encoding="utf-8"))
jobs=d.get("jobs") or []
en=[x for x in jobs if x.get("enabled")]
bad=[x for x in en if int((x.get("state") or {}).get("consecutiveErrors") or 0)>=1]
now=int(time.time()*1000)
over=[x for x in en if ((x.get("state") or {}).get("nextRunAtMs") or 0) and ((x.get("state") or {}).get("nextRunAtMs") or 0) < now-900000]
# 已复位（errs=0 但上次仍是 error）→ 不算 WARN，值里标 stale，等下次运行覆盖
stale=[x for x in en if int((x.get("state") or {}).get("consecutiveErrors") or 0)==0
       and str((x.get("state") or {}).get("lastRunStatus") or "") in ("error","failed")]
names=",".join(((x.get("name") or "")[:12]) for x in (bad+over)[:4])
snames=",".join(((x.get("name") or "")[:12]) for x in stale[:3])
if bad or over:
    print("WARN enabled=%d bad=%d overdue=%d stale=%d [%s]" % (len(en),len(bad),len(over),len(stale),names))
elif stale:
    print("PASS enabled=%d bad=0 overdue=0 stale=%d[%s]" % (len(en),len(stale),snames))
else:
    print("PASS enabled=%d bad=0 overdue=0" % len(en))