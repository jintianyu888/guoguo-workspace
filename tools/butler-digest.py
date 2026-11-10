#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''butler-digest.py — 跨管家周蒸馏（零 token）

只收三类有证据的句子：带证据的结论、踩过的坑/根因、被纠正过的口径。
每源最多 3 条、总计最多 12 条；全文写 state/briefs/，MEMORY.md 只留 <=10 行指针。
写 MEMORY.md 前：flock 独占、标记计数必须各 1、原子替换、留备份；任何异常一律中止不动文件。
'''

import argparse, fcntl, os, re, shutil, sqlite3, sys, tempfile, time
from datetime import datetime, timedelta

WS = '/home/j/.openclaw/workspace'
SELF = os.path.join(WS, 'state', 'self-review')
BRIEF = os.path.join(WS, 'state', 'briefs')
MEM = os.path.join(WS, 'MEMORY.md')
DB = os.path.join(WS, 'state', 'tasks', 'tasks.db')
BEGIN = '<!-- BUTLER-DIGEST:BEGIN -->'
END = '<!-- BUTLER-DIGEST:END -->'

PIT = re.compile(r'坑|教训|根因|误判|踩过|假绿|误读')
FIX = re.compile(r'纠正|更正|口径|以.{0,6}为准')
EVID = re.compile(r'rc=\d|\d+(\.\d+)?\s*(s|ms|G|MB|GB|条|次|分钟|小时)|/|\.py|\.sh|\b通过\b|\b完成\b|\b已修\b|\b走通\b|实测')


def clean(s):
    s = s.replace('**', '').replace('`', '')
    s = re.sub(r'^[#>*\-]+\s*', '', s)
    return s.strip()


def norm(s):
    return re.sub(r'[\s，。、：；！？,.:;!?]', '', s)[:60]


def collect_self_reviews(days=7):
    items, seen = [], set()
    if not os.path.isdir(SELF):
        return items
    cutoff = datetime.now() - timedelta(days=days)
    for fn in sorted(os.listdir(SELF)):
        p = os.path.join(SELF, fn)
        if not fn.endswith('.md') or not os.path.isfile(p):
            continue
        if datetime.fromtimestamp(os.path.getmtime(p)) < cutoff:
            continue
        try:
            lines = open(p, encoding='utf-8', errors='replace').read().splitlines()
        except OSError:
            continue
        for i, ln in enumerate(lines, 1):
            t = clean(ln.strip().lstrip('-*0123456789. '))
            if len(t) < 12 or len(t) > 200:
                continue
            if t.startswith('已完成扫描') or '无人值守' in t[:20]:
                continue
            if not (PIT.search(t) or FIX.search(t) or (t.startswith('DONE|') and EVID.search(t))):
                continue
            if not EVID.search(t):
                continue
            k = norm(t)
            if k in seen:
                continue
            seen.add(k)
            kind = 'pit' if PIT.search(t) else ('fix' if FIX.search(t) else 'done')
            items.append({'text': t.replace('DONE|', ''), 'src': '%s:%d' % (fn, i), 'kind': kind})
    return items


def collect_corrections(days=7):
    out = []
    if not os.path.exists(DB):
        return out
    try:
        c = sqlite3.connect('file:%s?mode=ro' % DB, uri=True, timeout=5)
        c.execute('pragma busy_timeout=3000')
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        rows = c.execute("select ts,no,field,new from events where ts>=? and (new like '%纠正%' or new like '%更正%' or new like '%错%') limit 20", (cutoff,)).fetchall()
        for ts, no, field, new in rows:
            s = clean(str(new))
            if 10 < len(s) < 160:
                out.append({'text': s, 'src': 'tasks.db#%s' % no, 'kind': 'fix'})
        c.close()
    except Exception:
        pass
    return out


def score(it):
    t = it['text']; s = 0
    if re.search(r'/|tools\.|\.py|\.sh|\.db', t): s += 3
    if re.search(r'\d+(\.\d+)?\s*(s|ms|G|MB|GB|条|次|分钟|小时)', t): s += 2
    if re.search(r'根因|教训|误判|假绿', t): s += 3
    if re.search(r'纠正|更正|以.{0,6}为准', t): s += 2
    if t.startswith('#'): s -= 5
    if len(t) > 140: s -= 2
    if it['kind'] == 'done': s -= 1
    return -s


def pick(items, per_src=3, total=12):
    order = {'pit': 0, 'fix': 1, 'done': 2}
    items.sort(key=lambda x: (score(x), order.get(x['kind'], 9), len(x['text'])))
    bucket, out = {}, []
    for it in items:
        src = it['src'].split(':')[0].split('#')[0]
        if bucket.get(src, 0) >= per_src:
            continue
        bucket[src] = bucket.get(src, 0) + 1
        out.append(it)
        if len(out) >= total:
            break
    return out


def render(items, week):
    L = ['# 跨管家周摘要 %s（生成 %s）' % (week, datetime.now().strftime('%Y-%m-%d %H:%M')), '']
    if not items:
        L.append('（本周没有可收的条目）')
    for it in items:
        L.append('- [%s] %s（%s）' % (it['kind'], it['text'], it['src']))
    return '\n'.join(L) + '\n'


def _block(items, week):
    L = [BEGIN, '### 跨管家周摘要 %s（自动生成，只读指针）' % week]
    for it in items[:10]:
        L.append('- %s（%s）' % (it['text'][:110], it['src']))
    L.append('全文：state/briefs/butler-weekly-%s.md' % week)
    L.append(END)
    return '\n'.join(L)


def _prune_backups(keep=8):
    d = os.path.join(WS, 'state', 'rollback')
    try:
        fs = sorted(f for f in os.listdir(d) if f.startswith('MEMORY.md.digest-'))
        for f in fs[:-keep]:
            os.remove(os.path.join(d, f))
    except OSError:
        pass


def merge_memory(items, week):
    if not items:
        return '没有新条目，MEMORY.md 未改动'
    if not os.path.exists(MEM):
        return 'MEMORY.md 不存在，跳过'
    lock_path = os.path.join(WS, 'state', 'work', '.butler-digest.lock')
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    lf = open(lock_path, 'w')
    deadline = time.time() + 30
    while True:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.time() > deadline:
                lf.close()
                return '拿不到锁（30s），本次跳过写 MEMORY.md'
            time.sleep(0.5)
    try:
        body = open(MEM, encoding='utf-8').read()
        nb, ne = body.count(BEGIN), body.count(END)
        if nb == 0 and ne == 0:
            new_body = body.rstrip() + '\n\n' + _block(items, week) + '\n'
        elif nb == 1 and ne == 1 and body.index(BEGIN) < body.index(END):
            pre = body.split(BEGIN)[0]
            post = body.split(END, 1)[1]
            new_body = pre + _block(items, week) + post
        else:
            return '标记异常（BEGIN=%d END=%d），已中止，MEMORY.md 未改动' % (nb, ne)
        if new_body == body:
            return '内容无变化'
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        bak = os.path.join(WS, 'state', 'rollback', 'MEMORY.md.digest-%s.bak' % stamp)
        os.makedirs(os.path.dirname(bak), exist_ok=True)
        shutil.copy2(MEM, bak)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MEM), prefix='.MEMORY.', suffix='.tmp')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(new_body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, MEM)
        _prune_backups()
        return 'MEMORY.md 已更新（%d 行指针），备份 %s' % (min(len(items), 10), os.path.basename(bak))
    finally:
        fcntl.flock(lf, fcntl.LOCK_UN)
        lf.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='写 state/briefs 并更新 MEMORY.md 指针')
    ap.add_argument('--days', type=int, default=7)
    a = ap.parse_args()
    week = datetime.now().strftime('%G-W%V')
    items = pick(collect_self_reviews(a.days) + collect_corrections(a.days))
    text = render(items, week)
    if a.write:
        os.makedirs(BRIEF, exist_ok=True)
        path = os.path.join(BRIEF, 'butler-weekly-%s.md' % week)
        open(path, 'w', encoding='utf-8').write(text)
        print(merge_memory(items, week))
        print('全文：' + path)
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
