#!/usr/bin/env python3
"""longtask-guard.py v2 —— 长任务保完成（L3 重活）

主公 2026-11-21 令：长任务必须保完成；失败先查因、再解决、再补跑；优先级最高（尤其备份）。

规则：
1. 平均耗时 >=600s 的启用任务视为长任务（jobs.db 近30天）。
2. 判定异常：从未运行 / 最近一次失败 / 超期未跑（日26h、周8d、月33d）。
3. 在夜间窗 00:30-07:30 → 立即补跑（每任务每天最多 2 次）。
   不在窗内 → 写入待补队列，理由写清，绝不白天拉重活。
4. 'interrupted'（网关重启打断）不算失败，进队列等窗内补。
5. 上游（全量备份）失败 → 下游（哈希/镜像/保留）挂起只报一条。
6. 补跑 2 次仍不成 → P0 推送，带原因，交人处理。
"""
import json, os, shutil, sqlite3, subprocess, sys
from datetime import datetime, timezone, timedelta

W = '/home/j/.openclaw/workspace'
DB = os.path.join(W, 'state/ledger/jobs.db')
TMP = '/tmp/jobs-guard.db'
STATE = os.path.join(W, 'state/work/longtask-guard.json')
QUEUE = os.path.join(W, 'state/work/longtask-queue.json')
LOG = os.path.join(W, 'state/work/longtask-failures.jsonl')
CST = timezone(timedelta(hours=8))
HEAVY_IO = ('备份', '镜像', '哈希', '快照', '归档')
# 会终止/重启本机的任务：绝对不能自动补跑，只报警
NEVER_RETRY = ('WSL整机镜像', '整机镜像', '重启', '关机', '压缩')
UPSTREAM = {
    '每日全量备份归档': ['备份哈希清单(每日)', '备份镜像+校验(每日)', '归档哈希+保留(每周六)', '周末全量备份归档'],
    '周末全量备份归档': ['备份镜像+校验(每日)'],
}
CADENCE = {'daily': 26, 'weekly': 24 * 8, 'monthly': 24 * 33}


def now():
    return datetime.now(CST)


def load_json(p, d):
    try:
        return json.load(open(p))
    except Exception:
        return d


def dump_json(p, v):
    tmp = p + '.tmp'
    json.dump(v, open(tmp, 'w'), ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def load_jobs():
    js = json.loads(subprocess.run(['openclaw', 'cron', 'list', '--json'],
                                   capture_output=True, text=True).stdout)
    return js['jobs'] if isinstance(js, dict) else js


def cadence(expr):
    p = (expr or '').split()
    if len(p) < 5:
        return 'daily'
    if p[4] != '*':
        return 'weekly'
    if p[2] != '*':
        return 'monthly'
    return 'daily'


def db_copy():
    shutil.copy(DB, TMP)
    return sqlite3.connect(TMP)


def heavy():
    out = {}
    if not os.path.exists(DB):
        return out
    c = db_copy()
    for n, a in c.execute("select name,avg(seconds) from runs where started > datetime('now','-30 days') group by name"):
        out[n] = a or 0
    c.close()
    return {n: a for n, a in out.items() if a >= 600}


def last_run(name):
    c = db_copy()
    row = c.execute("select status,started,seconds,error from runs where name=? order by started desc limit 1",
                    (name,)).fetchone()
    c.close()
    return row


def in_window(t=None):
    t = t or now()
    m = t.hour * 60 + t.minute
    return 30 <= m <= 450   # 00:30-07:30


def notify(msg):
    subprocess.run(['bash', os.path.join(W, 'tools/notify.sh'), '--p0', msg], capture_output=True, text=True)


def log(rec):
    with open(LOG, 'a') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def run_job(jid):
    try:
        r = subprocess.run(['openclaw', 'cron', 'run', jid], capture_output=True, text=True, timeout=180)
        return r.returncode == 0, (r.stderr or r.stdout or '')[:200]
    except Exception as e:
        return False, str(e)[:200]


def main():
    today = now().strftime('%Y-%m-%d')
    st = {k: v for k, v in load_json(STATE, {}).items() if v.get('date') == today}
    queue = load_json(QUEUE, {})
    jobs = {j.get('name'): j for j in load_jobs() if j.get('enabled')}
    hv = heavy()
    targets = sorted([(n, a) for n, a in hv.items() if n in jobs], key=lambda x: -x[1])

    failed_up, held, problems, queued, retried = set(), [], [], [], []
    for name, avg in targets:
        j = jobs[name]
        expr = (j.get('schedule') or {}).get('expr') or ''
        tol = CADENCE[cadence(expr)]
        stt = (j.get('state') or {})
        last_status = (j.get('lastRunStatus') or stt.get('lastRunStatus') or '').lower()
        last_err = j.get('lastRunError') or stt.get('lastError') or ''
        next_ms = j.get('nextRunAtMs') or stt.get('nextRunAtMs') or 0
        last_ms = j.get('lastRunAtMs') or stt.get('lastRunAtMs') or 0
        age_h = (now().timestamp() * 1000 - last_ms) / 3600000 if last_ms else None
        overdue = next_ms and next_ms < now().timestamp() * 1000
        reason, kind = None, None
        ENV = ('gateway stopping', 'owner is unav', 'restart')
        if not last_ms and not next_ms:
            reason, kind = '从未运行', 'never'
        elif any(e in (last_err or '').lower() for e in ENV) or last_status in ('interrupted', 'skipped'):
            # 最新的那次运行被打断，就等于这次没跑成 → 一律排补（队列自动去重）
            reason, kind = '上次被环境打断（%s），待补' % (last_err or last_status)[:80], 'deferred'
        elif last_status in ('error', 'failed', 'timeout'):
            reason, kind = '最近一次 %s：%s' % (last_status, (last_err or '')[:120]), 'failed'
        elif overdue and (age_h is None or age_h > tol):
            reason, kind = '排程未触发（上次 %.0f 小时前）' % (age_h or 0), 'missed'

        up = [u for u, down in UPSTREAM.items() if name in down]
        if up and any(u in failed_up for u in up):
            held.append(name)
            continue
        if not reason:
            queue.pop(name, None)
            continue
        if name in UPSTREAM and kind == 'failed':
            failed_up.add(name)
        if any(k in name for k in NEVER_RETRY):
            if not rec.get('notified'):
                problems.append((name, reason + '｜属停机类任务，禁止自动补跑，需人工在夜间窗确认'))
                rec['notified'] = today
            st[name] = rec
            queue.pop(name, None)
            continue

        rec = st.get(name, {'date': today, 'attempts': 0})
        rec['date'] = today
        is_io = any(k in name for k in HEAVY_IO)
        # 白天不拉重活：入队等夜间窗
        # 12 小时内本来就会再跑一次 → 不重复拉，等它自己跑
        soon = next_ms and (next_ms - now().timestamp() * 1000) < 12 * 3600 * 1000
        if soon and kind != 'never':
            st[name] = rec
            queue.pop(name, None)
            continue
        if kind == 'deferred' or (is_io and not in_window()) or not in_window():
            if name not in queue:
                queue[name] = {'since': now().isoformat(), 'reason': reason, 'jid': j['id']}
                queued.append((name, reason))
        else:
            if rec.get('attempts', 0) < 2:
                rec['attempts'] = rec.get('attempts', 0) + 1
                ok, msg = run_job(j['id'])
                retried.append((name, rec['attempts'], ok))
                log({'ts': now().isoformat(), 'job': name, 'act': 'retry',
                     'attempt': rec['attempts'], 'reason': reason, 'rc': 0 if ok else 1, 'msg': msg})
                if not ok:
                    problems.append((name, reason + '｜补跑触发失败'))
            else:
                problems.append((name, reason + '｜今日已补 2 次仍不成'))
        st[name] = rec

    # 窗内冲队列
    flushed = []
    if in_window():
        for name, item in list(queue.items()):
            j = jobs.get(name)
            if not j:
                queue.pop(name, None)
                continue
            rec = st.get(name, {'date': today, 'attempts': 0})
            if rec.get('attempts', 0) >= 2:
                problems.append((name, item.get('reason', '') + '｜排队后仍补跑 2 次不成'))
                queue.pop(name, None)
                continue
            rec['attempts'] = rec.get('attempts', 0) + 1
            st[name] = rec
            ok, msg = run_job(j['id'])
            flushed.append((name, ok))
            log({'ts': now().isoformat(), 'job': name, 'act': 'flush', 'attempt': rec['attempts'],
                 'reason': item.get('reason', ''), 'rc': 0 if ok else 1, 'msg': msg})
            if ok:
                queue.pop(name, None)
            elif rec['attempts'] >= 2:
                problems.append((name, item.get('reason', '') + '｜补跑 2 次失败'))
                queue.pop(name, None)

    dump_json(STATE, st)
    dump_json(QUEUE, queue)

    if problems:
        lines = ['【长任务未完成 · 必须处理】' + now().strftime('%m-%d %H:%M')]
        for n, r in problems[:8]:
            lines.append('· %s：%s' % (n, r))
        if held:
            lines.append('下游已挂起：' + '、'.join(held[:6]))
        notify('\n'.join(lines))
        print('\n'.join(lines))
        return 1

    if queued:
        print('已排入夜间补跑：' + '、'.join(n for n, _ in queued))
    if flushed:
        print('窗内补跑：' + '、'.join('%s%s' % (n, 'OK' if ok else 'FAIL') for n, ok in flushed))
    if retried:
        print('即时补跑：' + '、'.join('%s(%d)' % (n, a) for n, a, _ in retried))
    if not (queued or flushed or retried):
        print('长任务全部在期：%d 项' % len(targets))
    return 0


if __name__ == '__main__':
    sys.exit(main())
