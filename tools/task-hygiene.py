#!/usr/bin/env python3
# task-hygiene.py v1.1 — 待办复核（零 token）
import json,os,datetime,sqlite3,shutil
W='/home/j/.openclaw/workspace'; shutil.copy(W+'/state/tasks/tasks.db','/tmp/hyg.db')
c=sqlite3.connect('/tmp/hyg.db'); today=datetime.date.today()
rows=c.execute("select no,status,grp,title,due_plan,who,wait_user,notes from tasks where status in ('pending','in_progress') order by no").fetchall()
out=[]
for no,st,grp,title,due,who,wu,notes in rows:
    age=None
    try:
        if due: age=(today-datetime.date.fromisoformat(str(due)[:10])).days
    except Exception: pass
    flag='🔴超期%d天'%age if (age is not None and age>2) else ('⚠️%d天'%age if age is not None and age>0 else 'ok')
    out.append(dict(no=no,status=st,grp=grp or '-',title=(title or '')[:55],due=due,flag=flag,wait_user=bool(wu)))
json.dump(dict(date=str(today),open_count=len(out),items=out),open(W+'/state/work/task-hygiene.json','w'),ensure_ascii=False,indent=1)
print('未结',len(out))
for i in out: print(' ',i['no'],i['status'],i['flag'],i['title'])
if len(out)>6: print('⚠️ 超上限6条')