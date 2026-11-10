#!/usr/bin/env python3
"""approval-board.py —— 待批台（账本为唯一真源，不引入第二真源）
子命令：
  list                列出当前待批项（编号=序号，非账本 no）
  apply "1-3 批, 5 缓"  按序号批量回写账本
  push                生成一张待批卡片文本（有事才推：无事输出空）
设计要点：账本是唯一真源；卡片只是视图；解析支持 批/准/同意、缓/暂缓、否/驳回。
"""
import json,os,re,sys,time

WS='/home/j/.openclaw/workspace'
LED=os.path.join(WS,'state/tasks/tasks.json')
LOG=os.path.join(WS,'state/work/approval-board.jsonl')

def load():
    return json.load(open(LED,encoding='utf-8'))

def save(d):
    t=LED+'.tmp'
    json.dump(d,open(t,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    os.replace(t,LED)

def need_approval(i):
    if i.get('status')!='pending': return False
    t=str(i.get('title') or '')
    return i.get('kind')=='decision' or t.startswith('【待拍板】') or '需主公' in t

def items(d):
    return [i for i in d['items'] if isinstance(i,dict) and need_approval(i)]

def cmd_list():
    d=load(); its=items(d)
    if not its:
        print('（无待批项）'); return
    for n,i in enumerate(its,1):
        print('%2d. [账本%s] %s'%(n,i.get('no'),str(i.get('title'))[:70]))

def cmd_push():
    d=load(); its=items(d)
    if not its:
        print('')  # 无事静默
        return
    lines=['待批 %d 项（回「1-3 批 / 5 缓」即可）'%len(its)]
    for n,i in enumerate(its,1):
        lines.append('%d. %s'%(n,str(i.get('title'))[:60]))
    print('\n'.join(lines))

def parse_cmds(text):
    out=[]
    for m in re.finditer(r'(\d+)\s*(?:[-~到]\s*(\d+))?\s*(批|准|同意|缓|暂缓|否|驳回)', text):
        a=int(m.group(1)); b=int(m.group(2) or a); verb=m.group(3)
        action={'批':'approve','准':'approve','同意':'approve','缓':'hold','暂缓':'hold','否':'reject','驳回':'reject'}[verb]
        out.append((a,b,action))
    return out

def cmd_apply(text):
    d=load(); its=items(d); now=time.strftime('%Y-%m-%dT%H:%M:%S+08:00')
    cmds=parse_cmds(text)
    if not cmds:
        print('无法解析：请用「1-3 批 / 5 缓」这种格式'); return 2
    changed=[]
    for a,b,act in cmds:
        for n in range(a,b+1):
            if n<1 or n>len(its): continue
            it=its[n-1]
            if act=='approve':
                it['status']='in_progress'; note='主公批准（待批台）'
            elif act=='hold':
                it['status']='paused'; note='主公暂缓（待批台）'
            else:
                it['status']='cancelled'; note='主公驳回（待批台）'
            it['notes']=(it.get('notes') or '')+'｜%s %s'%(now,note)
            it['updated']=now
            changed.append((n,it.get('no'),act))
    d['updated']=now
    if changed:
        save(d)
        with open(LOG,'a',encoding='utf-8') as f:
            f.write(json.dumps({'at':now,'raw':text,'changed':changed},ensure_ascii=False)+'\n')
    for c in changed: print('已处理 #%d 账本%s -> %s'%c)
    return 0

if __name__=='__main__':
    cmd=sys.argv[1] if len(sys.argv)>1 else 'list'
    if cmd=='list': cmd_list()
    elif cmd=='push': cmd_push()
    elif cmd=='apply':
        sys.exit(cmd_apply(' '.join(sys.argv[2:])))
    else:
        print('用法: approval-board.py list|push|apply "1-3 批, 5 缓"'); sys.exit(64)
