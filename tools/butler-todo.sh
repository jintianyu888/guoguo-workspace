#!/usr/bin/env bash
# butler-todo.sh —— 五大管家待办登记（果果助手看板「五大管家待办」栏数据源）
# 用法：
#   butler-todo.sh add <管家id> "<事项>" [doing|todo|blocked|wait|done]
#   butler-todo.sh done <管家id> <序号>
#   butler-todo.sh list [管家id]
# 管家 id：maint 维护 / backup 备份 / model 模型 / work 干活 / sheet-music Hermess
set -euo pipefail
F=/home/j/openclaw-workspaces/work/果果助手/public/butler-todos.json
exec python3 - "$F" "$@" <<'PY'
import json,sys,os,datetime
f=sys.argv[1]; act=sys.argv[2] if len(sys.argv)>2 else 'list'
names={'maint':'维护','backup':'备份','model':'模型','work':'干活','sheet-music':'Hermess'}
ST={'doing':'进行中','todo':'待办','blocked':'受阻','wait':'待确认','done':'完成'}
def load():
    if os.path.exists(f):
        return json.load(open(f,encoding='utf-8'))
    return {'updated':'','butlers':[{'id':k,'name':v,'items':[]} for k,v in names.items()]}
def save(d):
    d['updated']=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    tmp=f+'.tmp'
    json.dump(d,open(tmp,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    os.replace(tmp,f)
def grp(d,aid):
    for b in d['butlers']:
        if b['id']==aid: return b
    b={'id':aid,'name':names.get(aid,aid),'items':[]}
    d['butlers'].append(b); return b
now=datetime.datetime.now().astimezone().isoformat(timespec='minutes')
if act=='add':
    aid=sys.argv[3]; text=sys.argv[4]; st=sys.argv[5] if len(sys.argv)>5 else 'todo'
    if st not in ST: print('状态必须是 '+'/'.join(ST)); sys.exit(2)
    d=load(); b=grp(d,aid)
    b['items'].append({'text':text,'status':st,'updated':now})
    save(d); print('OK %s 已登记：%s（%s）'%(aid,text,ST[st]))
elif act=='done':
    aid=sys.argv[3]; idx=int(sys.argv[4])
    d=load(); b=grp(d,aid)
    if not (1<=idx<=len(b['items'])): print('序号超范围'); sys.exit(2)
    b['items'][idx-1]['status']='done'; b['items'][idx-1]['updated']=now
    save(d); print('OK 已置完成：%s'%b['items'][idx-1]['text'])
elif act=='list':
    d=load()
    for b in d['butlers']:
        print('【%s】%d 条'%(b['name'],len(b['items'])))
        for i,it in enumerate(b['items'],1):
            print('  %d. [%s] %s'%(i,ST.get(it['status'],it['status']),it['text']))
else:
    print('用法: add|done|list'); sys.exit(2)
PY
