#!/usr/bin/env python3
"备份额外站 _trash 自动清理：仅删「有同名同大小副本」且「落trash超过 N 天」的归档；默认 dry-run。"
"""用法: backup-trash-purge.py [--apply] [--days 3] [--max 6]"""
import os, sys, glob, json, time, subprocess, argparse
TRASH_DIRS=['/mnt/d/openclaw-backups/_trash','/mnt/e/openclaw-backups/_trash','/mnt/h/openclaw-backups/_trash']
REPLICAS={'E':'/mnt/e/openclaw-backups','H':'/mnt/h/openclaw-backups'}
NAS='nas'; NAS_DIR='/var/services/homes/guoguonas/archive/jinyu/openclaw-archives'
LED='/home/j/.openclaw/workspace/state/trash-ledger.jsonl'
def idx(base):
    d={}
    for p in glob.glob(os.path.join(base,'*.tar.gz')):
        try: d[os.path.basename(p)]=os.path.getsize(p)
        except OSError: pass
    return d
def nas_idx(names):
    if not names: return {}
    q='for n in '+' '.join(n.split('+')[0] for n in names)+'; do f=$(ls '+NAS_DIR+'/${n}*openclaw-backup.tar.gz 2>/dev/null|head -1); [ -n "$f" ] && echo "$(basename $f)|$(stat -c%s $f)"; done'
    out=subprocess.run(['timeout','40','ssh','-o','ConnectTimeout=8',NAS,q],capture_output=True,text=True).stdout
    d={}
    for line in out.splitlines():
        if '|' in line:
            nm,sz=line.rsplit('|',1)
            try: d[nm]=int(sz)
            except ValueError: pass
    return d
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--apply',action='store_true')
    ap.add_argument('--days',type=int,default=3)
    ap.add_argument('--max',type=int,default=6)
    a=ap.parse_args()
    rep={k:idx(v) for k,v in REPLICAS.items()}
    items=[]
    for t in TRASH_DIRS:
        for p in sorted(glob.glob(os.path.join(t,'*','*.tar.gz'))):
            try: st=os.stat(p)
            except OSError: continue
            age=(time.time()-st.st_mtime)/86400
            if age < a.days: continue
            items.append((p,os.path.basename(p),st.st_size,age))
    if not items:
        print('trash 内没有超过 %d 天的归档' % a.days); return 0
    nd=nas_idx([i[1] for i in items])
    plan=[]
    for p,nm,s,age in items:
        src=None
        for k,v in rep.items():
            if v.get(nm)==s: src=k; break
        if not src and nd.get(nm)==s: src='NAS'
        plan.append((p,nm,s,age,src))
    cand=[x for x in plan if x[4]][:a.max]
    nover=[x for x in plan if not x[4]]
    freed=sum(x[2] for x in cand)
    print('候选 %d 个 / %.1fG；无副本保留 %d 个' % (len(cand), freed/2**30, len(nover)))
    for p,nm,s,age,src in cand: print('  %.1fG 副本%-3s %4.1f天 %s' % (s/2**30,src,age,nm[:38]))
    if not a.apply:
        print('[dry-run] 加 --apply 执行'); return 0
    done=[]
    for p,nm,s,age,src in cand:
        try: os.remove(p); done.append((nm,s,src))
        except OSError as e: print('删除失败',nm,e)
    if done:
        with open(LED,'a') as f:
            f.write(json.dumps({'ts':time.strftime('%Y-%m-%dT%H:%M:%S'),'action':'auto-purge-trash','freed_bytes':sum(d[1] for d in done),'items':[{'name':d[0],'bytes':d[1],'copy':d[2]} for d in done]},ensure_ascii=False)+chr(10))
    print('已删 %d 个 / %.1fG' % (len(done), sum(d[1] for d in done)/2**30))
    return 0
if __name__=='__main__': sys.exit(main())