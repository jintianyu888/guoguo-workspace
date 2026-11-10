#!/usr/bin/env python3
# ledger-audit.py —— 唯一账本对账（只读）rc=0 无缺口 / rc=1 有缺口
import sqlite3,os,sys,json,subprocess,time
W='/home/j/.openclaw/workspace'
DB=W+'/state/ledger/ledger.db'
if '--db' in sys.argv:
    DB=sys.argv[sys.argv.index('--db')+1]
c=sqlite3.connect(DB)
gaps=[]
rows=list(c.execute("select script_id,path,purpose,registered from scripts_v2"))
print('脚本入账:',len(rows))
nop=[r for r in rows if not (r[2] or '').strip()]
if nop: gaps.append(('无用途说明',len(nop),'legacy'))
jobs=list(c.execute("select job_id,name,script_path,payload_kind from cron_jobs"))
unmapped=[j for j in jobs if not j[2] and (j[3] if len(j)>3 else '') != 'agentTurn']
if unmapped: gaps.append(('cron 未映射脚本',len(unmapped),'legacy'))
missing=[j for j in jobs if j[2] and not os.path.exists(os.path.join(W,j[2]))]
if missing: gaps.append(('cron 指向不存在的脚本',len(missing),'legacy'))
tasks=list(c.execute('select task_id,title,status,verify_cmd from tasks'))
opent=[t for t in tasks if str(t[2]).lower() not in ('done','closed','archived','已结','已关闭')]
nov=[t for t in opent if not (t[3] or '').strip()]
if nov: gaps.append(('未结任务无可验证命令',len(nov),'legacy'))

# ================= 新账本校验（2026-11-01 立）=================
def _exists(name):
    return bool(list(c.execute("select 1 from sqlite_master where type='table' and name=?", (name,))))

def _common_fields(table, label):
    out=[]
    if not _exists(table):
        out.append((label+"表不存在", 0, "hard")); return out
    nw=list(c.execute("select count(*) from "+table+" where writer is null or trim(writer)=''"))[0][0]
    nt=list(c.execute("select count(*) from "+table+" where trace_id is null or trim(trace_id)=''"))[0][0]
    nh=list(c.execute("select count(*) from "+table+" where content_sha256 is null or trim(content_sha256)=''"))[0][0]
    if nw: out.append((label+"缺 writer", nw, "hard"))
    if nt: out.append((label+"缺 trace_id", nt, "hard"))
    if nh: out.append((label+"缺 content_sha256", nh, "hard"))
    return out

# --- ledger_events：按 source 分组，各自独立链 ---
ev_gaps=[]
if _exists("ledger_events"):
    ev_gaps += _common_fields("ledger_events","事件账 ")
    srcs=[r[0] for r in c.execute("select distinct source from ledger_events")]
    tot_fork=0; tot_break=0
    for src in srcs:
        forks=list(c.execute("select prev_hash,count(*) n from ledger_events where source=? and prev_hash is not null group by prev_hash having n>1",(src,)))
        rows=list(c.execute("select content_sha256,prev_hash from ledger_events where source=? order by orig_line",(src,)))
        brk=sum(1 for i in range(1,len(rows)) if rows[i][1]!=rows[i-1][0])
        head_bad=sum(1 for r in rows[:1] if r[1] is not None)
        tot_fork+=len(forks); tot_break+=brk+head_bad
        # 水位一致性
        wm=list(c.execute("select migrated_lines from ledger_migrations where source=?",(src,)))
        if wm and wm[0][0]!=len(rows):
            ev_gaps.append(("事件账水位不符 "+src, "%d vs %d"%(wm[0][0],len(rows)), "hard"))
    if tot_fork: ev_gaps.append(("事件账链分叉", tot_fork, "hard"))
    if tot_break: ev_gaps.append(("事件账链断裂/截断", tot_break, "hard"))
    print("事件账: 来源",len(srcs),"个 | 分叉",tot_fork,"| 断链",tot_break)
else:
    ev_gaps.append(("事件账表不存在", 0, "hard")); print("事件账: 表不存在")

# --- model_policy：单条全局链，按 id 排序 ---
mp_gaps=[]
if _exists("model_policy"):
    mp_gaps += _common_fields("model_policy","模型策略账 ")
    rows=list(c.execute("select content_sha256,prev_hash from model_policy order by id"))
    brk=sum(1 for i in range(1,len(rows)) if rows[i][1]!=rows[i-1][0])
    head_bad=sum(1 for r in rows[:1] if r[1] is not None)
    forks=list(c.execute("select prev_hash,count(*) n from model_policy where prev_hash is not null group by prev_hash having n>1"))
    if forks: mp_gaps.append(("模型策略账链分叉", len(forks), "hard"))
    if brk+head_bad: mp_gaps.append(("模型策略账链断裂/截断", brk+head_bad, "hard"))
    print("模型策略账: 条数",len(rows),"| 分叉",len(forks),"| 断链",brk+head_bad)
else:
    mp_gaps.append(("模型策略账表不存在", 0, "hard")); print("模型策略账: 表不存在")

gaps += ev_gaps + mp_gaps

print('cron:',len(jobs),'| 任务:',len(tasks),'| 未结:',len(opent))
print()
hard = [g for g in gaps if len(g) > 2 and g[2] == 'hard']
legacy = [g for g in gaps if not (len(g) > 2 and g[2] == 'hard')]
if legacy:
    print('【历史遗留·仅告警】')
    for g in legacy: print(f'  {g[0]}: {g[1]}')

    print('\n示例:')
    for j in unmapped[:5]: print('  cron无脚本:',j[1])
    for j in missing[:3]: print('  指向不存在:',j[1],'->',j[2])
    for t in nov[:5]: print('  任务无验证命令: #%s %s'%(t[0],str(t[1])[:40]))
else:
    print('【账本缺口】无 ✅')
env_bad = [g for g in hard if ("表不存在" in str(g[0]) or "缺失" in str(g[0]))]
if hard:
    print()
    print("【新账本缺口·必须处理】")
    for g in hard:
        print("  " + str(g[0]) + ": " + str(g[1]))
if env_bad:
    print()
    print("【审计环境异常】关键账本表缺失，本次审计不可信 -> rc=2")
    sys.exit(2)
# 退出码约定：0=通过 1=有hard缺口 2=审计器自身/环境异常
sys.exit(1 if hard else 0)
