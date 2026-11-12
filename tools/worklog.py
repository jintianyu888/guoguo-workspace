#!/usr/bin/env python3
# worklog.py — 统一工作日志（2026-11-10 主公令：所有事情都要入账）
# 机器账本：state/log/worklog.jsonl（追加写，带前序哈希链）
# 人读日报：docs/工作日志-YYYY-MM.md（由本脚本整体重渲染，可进 git）
# 用法：worklog.py add <类别> <对象> <结果> [evidence=] [rollback=] [task=] [actor=] [rc=]
#       worklog.py render [YYYY-MM] / check / tail [N]
import os, sys, json, hashlib, datetime, sqlite3

W = '/home/j/.openclaw/workspace'
LED = os.path.join(W, 'state/log/worklog.jsonl')
DOCS = os.path.join(W, 'docs')
BT = chr(96)
CATS = {'fix', 'change', 'cleanup', 'deploy', 'decision', 'incident', 'verify', 'note', 'plan'}

def now():
    return datetime.datetime.now().isoformat(timespec='seconds')

def last_hash():
    if not os.path.exists(LED):
        return 'genesis'
    last = None
    with open(LED) as f:
        for line in f:
            if line.strip():
                last = line
    if not last:
        return 'genesis'
    try:
        return json.loads(last).get('hash', 'genesis')
    except Exception:
        return 'genesis'

def load():
    out = []
    if os.path.exists(LED):
        with open(LED) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
    return out

def append(rec):
    os.makedirs(os.path.dirname(LED), exist_ok=True)
    prev = last_hash()
    rec['prev'] = prev
    body = json.dumps({k: v for k, v in rec.items() if k != 'hash'}, ensure_ascii=False, sort_keys=True)
    rec['hash'] = hashlib.sha256((prev + '|' + body).encode()).hexdigest()[:16]
    with open(LED, 'a') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    return rec

def cmd_add(argv):
    if len(argv) < 3:
        print('用法: worklog.py add <类别> <对象> <结果> [k=v ...]')
        return 2
    cat, target, summary = argv[0], argv[1], argv[2]
    if cat not in CATS:
        print('类别必须是: ' + ' '.join(sorted(CATS)))
        return 2
    rec = {'ts': now(), 'actor': '果果', 'cat': cat, 'target': target,
           'summary': summary, 'evidence': '', 'rollback': '', 'task': '', 'rc': ''}
    for kv in argv[3:]:
        if '=' in kv:
            k, v = kv.split('=', 1)
            if k in rec:
                rec[k] = v
    if not rec['summary'].strip():
        print('结果不能为空')
        return 2
    # 2026-11-12 自纠错闭环（M-20261112-001）：绝对断言必须带证据
    import re as _re
    _claim = _re.search(r'已(经)?(生效|修复|完成|解决|部署|上线|恢复)|恢复正常|无风险|不会再?出现|全部(通过|正常)|一切正常', rec['summary'] + ' ' + rec['target'])
    if _claim and not rec['evidence'].strip():
        print('拒绝入账：出现绝对断言（%s）但没有 evidence=' % _claim.group(0))
        print('  补 evidence="命令与输出"，或把话说成"待验假设"')
        return 3
    r = append(rec)
    print('入账 %s %s/%s %s' % (r['ts'], r['cat'], r['target'], r['hash']))
    return 0

def cmd_render(argv):
    rows = load()
    if not rows:
        print('账本为空')
        return 0
    month = argv[0] if argv else datetime.date.today().strftime('%Y-%m')
    sel = [r for r in rows if r['ts'][:7] == month]
    os.makedirs(DOCS, exist_ok=True)
    p = os.path.join(DOCS, '工作日志-' + month + '.md')
    L = ['# 工作日志 ' + month + '（自动生成，源头 state/log/worklog.jsonl）', '']
    L.append('> 本文件由 tools/worklog.py render 从机器账本重渲染，禁止手改；每条含时间/类别/对象/结果/证据/回滚。')
    L.append('')
    cur = None
    for r in sel:
        d = r['ts'][:10]
        if d != cur:
            cur = d
            L.append('')
            L.append('## ' + d)
            L.append('')
        bits = ['- **' + r['ts'][11:19] + '**', BT + r['cat'] + BT, r['target'], '—', r['summary']]
        if r.get('task'):
            bits.append('（#' + str(r['task']) + '）')
        L.append(' '.join(bits))
        if r.get('evidence'):
            L.append('  - 证据：' + r['evidence'])
        if r.get('rollback'):
            L.append('  - 回滚：' + r['rollback'])
    L.append('')
    open(p, 'w').write('\n'.join(L))
    print('已渲染 %d 条 → %s' % (len(sel), p))
    return 0

def cmd_check(argv):
    rows = load()
    today = datetime.date.today().isoformat()
    n = len([r for r in rows if r['ts'][:10] == today])
    print('今日条目 %d 条（累计 %d）' % (n, len(rows)))
    db = os.path.join(W, 'state/tasks/tasks.db')
    if os.path.exists(db):
        c = sqlite3.connect('file:' + db + '?mode=ro', uri=True)
        closed = [str(no) for (no,) in c.execute(
            "select no from tasks where status='done' and substr(updated,1,10)=?", (today,))]
        logged = {str(r.get('task')) for r in rows if r['ts'][:10] == today and r.get('task')}
        miss = [x for x in closed if x not in logged]
        print('今日关单 %d 条；未挂 task= 的: %s' % (len(closed), ' '.join(miss) if miss else '无'))
    return 0

def cmd_tail(argv):
    n = int(argv[0]) if argv else 10
    for r in load()[-n:]:
        print(r['ts'], r['cat'], r['target'], '|', r['summary'][:70])
    return 0

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd, argv = sys.argv[1], sys.argv[2:]
    if cmd == 'add':
        return cmd_add(argv)
    if cmd == 'render':
        return cmd_render(argv)
    if cmd == 'check':
        return cmd_check(argv)
    if cmd == 'tail':
        return cmd_tail(argv)
    print('未知命令')
    return 2

if __name__ == '__main__':
    sys.exit(main())
