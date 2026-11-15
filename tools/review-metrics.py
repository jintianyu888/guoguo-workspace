#!/usr/bin/env python3
# review-metrics.py v1.0 — 互审质量度量（零 token）
import os,glob,json,datetime,re
W='/home/j/.openclaw/workspace'; R=W+'/state/review'
today=datetime.date.today(); rows=[]
for pair in sorted(glob.glob(R+'/*')):
    if not os.path.isdir(pair): continue
    days=sorted(glob.glob(pair+'/2*'))[-7:]
    for d in days:
        f=lambda n: os.path.exists(os.path.join(d,n))
        finals=glob.glob(d+'/final.md')
        ok=False; rounds=0; hi=0
        if finals:
            t=open(finals[0]).read(); ok='复核结论：合格' in t
        for rv in glob.glob(d+'/review-v*.md'):
            rounds+=1
            hi+=open(rv).read().count('严重度：高')+len(re.findall(r'【高】|\b[HR]\d+-H\d+',open(rv).read()))
        rows.append(dict(pair=os.path.basename(pair),date=os.path.basename(d),final=bool(finals),qualified=ok,reviews=rounds,high=hi))
due=[r for r in rows if r['date']>=str(today-datetime.timedelta(days=7))]
q=sum(1 for r in due if r['qualified']); f=sum(1 for r in due if r['final'])
high=sum(r['high'] for r in due); rev=sum(r['reviews'] for r in due)
out=dict(date=str(today),groups=len(due),completed=len({r['pair'] for r in due if r['final']}),
         qualification_rate=(round(q/len(due),2) if due else 0),high_findings=high,review_rounds=rev,
         note='high=0 说明没真审；定稿率<80% 或连续3天无定稿 → 该组合停用')
os.makedirs(W+'/state/review/_metrics',exist_ok=True)
json.dump(out,open(W+'/state/review/_metrics/latest.json','w'),ensure_ascii=False,indent=1)
print(json.dumps(out,ensure_ascii=False))