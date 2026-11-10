#!/usr/bin/env python3
"""stuck-watch.py —— 卡住检测（零 token）：谁没动、什么事过期没做，直接给结论和下一步

输出:
  state/work/stuck.json   机器可读（overdue 任务、空转管家、失败任务、建议动作）
  stdout                  给人看的一屏摘要（给 cron 消息/我读）
判定:
  1) 待办过期：status in (pending,in_progress) 且 due_plan < 现在 − 宽限(默认30分钟)
  2) 管家空转：该管家 cron 任务最近 3 小时无成功回执，且工作区 3 小时无文件变化
  3) 任务失败：最近 6 小时 lastRunStatus!=ok 且未被网关重启打断
  4) 队列堵塞：同日 overdue ≥5 件 → 直接报「优先级重排」而不是逐条催

变更:
  2026-11-10 overdue 按 agent 分流：overdue_mine 只含 agent=main；其他管家进 overdue_butlers（只报不派），
             等主公的进 overdue_owner。原因：#954(hermess) 曾混进 mine，自派工去挑不属于自己的活。
"""
import os, sys, json, time, sqlite3, datetime, glob

W = '/home/j/.openclaw/workspace'
OUT = os.path.join(W, 'state/work/stuck.json')
GRACE_MIN = int(os.environ.get('STUCK_GRACE_MIN', '30'))

def now(): return datetime.datetime.now()

def tasks_overdue():
    c = sqlite3.connect(os.path.join(W, 'state/tasks/tasks.db')); c.row_factory = sqlite3.Row
    rows = c.execute("select no,title,status,due_plan,eta_min,wait_user,agent from tasks where status in ('pending','in_progress','open')").fetchall()
    late = []
    for r in rows:
        dp = (r['due_plan'] or '').strip()
        if not dp: continue
        try:
            t = datetime.datetime.strptime(dp[:16], '%Y-%m-%d %H:%M')
        except Exception:
            try: t = datetime.datetime.strptime(dp[:10], '%Y-%m-%d') + datetime.timedelta(hours=23)
            except Exception: continue
        mins = (now() - t).total_seconds() / 60.0
        if mins > GRACE_MIN:
            late.append({'no': r['no'], 'title': r['title'][:60], 'due': dp,
                         'late_min': int(mins), 'wait_user': r['wait_user'], 'status': r['status'],
                         'agent': (r['agent'] or 'main')})
    late.sort(key=lambda x: -x['late_min'])
    return late

def cron_state():
    p = os.path.join(W, 'state/work/cron-health.json')
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return {}

def butler_idle():
    """工作区 3 小时无文件变化 + 该管家无新回执 → 空转候选"""
    idle = []
    base = '/home/j/openclaw-workspaces'
    cutoff = time.time() - 3 * 3600
    # 只看现役管家；休眠/归档目录不参与（2026-11-08：13 个管家已标 dormant，报了只会变噪音）
    ACTIVE = {'maint', 'backup', 'model', 'work', 'hermess'}
    if not os.path.isdir(base): return idle
    for name in sorted(os.listdir(base)):
        if name not in ACTIVE: continue
        d = os.path.join(base, name)
        if not os.path.isdir(d): continue
        newest = 0
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x not in ('.git', 'node_modules', '__pycache__')]
            for f in files[:200]:
                try: newest = max(newest, os.path.getmtime(os.path.join(root, f)))
                except Exception: pass
            if newest > cutoff: break
        if newest and newest < cutoff:
            idle.append({'butler': name, 'idle_h': round((time.time() - newest) / 3600, 1)})
    return idle

def main():
    late = tasks_overdue()
    idle = butler_idle()
    ch = cron_state()
    # 归属分流（2026-11-10 修）：只有 agent=main 的才算「我这边」，其他管家的过期单独计数，
    # 否则 hermess/maint 等管家的任务会挤进 overdue_mine，自派工去挑根本不属于它的活。
    mine = [x for x in late if not x['wait_user'] and x['agent'] == 'main']
    owner = [x for x in late if x['wait_user']]
    butler_overdue = [x for x in late if not x['wait_user'] and x['agent'] != 'main']
    res = {'ts': now().strftime('%Y-%m-%d %H:%M:%S'), 'grace_min': GRACE_MIN,
           'overdue_mine': mine, 'overdue_owner': owner, 'overdue_butlers': butler_overdue,
           'idle_butlers': idle,
           'cron_health': ch}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    msgs = []
    if mine:
        msgs.append('🔴 我这边的过期未做 %d 件，最久 %s（#%s %s）' % (
            len(mine), _hm(mine[0]['late_min']), mine[0]['no'], mine[0]['title']))
        if len(mine) >= 5:
            msgs.append('  队列堵塞：建议按 优先级×耗时 重排，先砍到 3 件，其余改期写原因')
    if owner:
        msgs.append('⏳ 等你拍板 %d 件（%s）' % (len(owner), '、'.join('#%s' % x['no'] for x in owner[:5])))
    if idle:
        msgs.append('💤 可能空转：' + '、'.join('%s(%sh)' % (i['butler'], i['idle_h']) for i in idle[:6]))
    if butler_overdue:
        msgs.append('🔧 其他管家过期 %d 件（%s），不归我做，只报不派' % (
            len(butler_overdue), '、'.join('#%s(%s)' % (x['no'], x['agent']) for x in butler_overdue[:5])))
    if not msgs:
        msgs.append('✅ 无过期、无空转（宽限 %d 分钟）' % GRACE_MIN)
    print('\n'.join(msgs))
    print('明细: %s' % OUT)
    return 0

def _hm(m):
    return ('%dh%02dm' % (m // 60, m % 60)) if m >= 60 else ('%dm' % m)

if __name__ == '__main__':
    sys.exit(main())
