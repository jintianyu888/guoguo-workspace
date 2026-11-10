import csv,datetime,os
p="state/usage-meter/daily.csv"
rows=list(csv.DictReader(open(p)))
def cost(day):
    s=0.0
    for r in rows:
        d=(r.get("date") or r.get("day") or "")[:10]
        if d==day:
            try: s+=float(r.get("cost") or r.get("cost_marginal") or 0)
            except: pass
    return s
t=datetime.date.today(); y=t-datetime.timedelta(days=1)
c1=cost(t.isoformat()); c0=cost(y.isoformat())
if c0<=0:
    print("PASS today=%.2f (no baseline)" % c1)
elif c1>c0*2:
    print("WARN today=%.2f yesterday=%.2f (>2x)" % (c1,c0))
else:
    print("PASS today=%.2f yesterday=%.2f" % (c1,c0))