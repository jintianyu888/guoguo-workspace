#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''eval-ledger.py — 评测/评审数据归一账本（state/eval/eval.db 为唯一真源）

来源：state/eval/*.json、state/eval/history/*.json、state/bench/*.json、
      state/work/cross-review/<提案>/*.txt、workspace-model/docs/交叉验证台账.md 表格
表：runs（模型能力/系统基线）、reviews（每次交叉评审的单个评审员结论）、proposals（提案级汇总）
追加：model-eval.py 与新评审脚本应调用 `eval-ledger.py add-run` / `add-review` 或直接写库。
'''

import argparse, glob, hashlib, json, os, re, sqlite3, sys
from datetime import datetime

WS = '/home/j/.openclaw/workspace'
DB = os.path.join(WS, 'state', 'eval', 'eval.db')
MODEL_WS = '/home/j/.openclaw/workspace-model'

DDL = '''
create table if not exists runs(
  id text primary key,            -- kind|evidence|subject|ts 的短哈希
  ts text, kind text,            -- bench | sysbench | longctx | probe
  suite text, provider text, model text,
  score real, score_max real, verdict text,
  latency_s real, cost_cny real,
  evidence text, evidence_sha text, note text, imported_at text);
create index if not exists ix_runs_subject on runs(provider, model, ts);
create index if not exists ix_runs_kind on runs(kind, ts);
create table if not exists reviews(
  id text primary key, ts text, proposal text, provider text, model text,
  verdict text, chars integer, evidence text, evidence_sha text, imported_at text);
create index if not exists ix_rev_model on reviews(provider, model, ts);
create table if not exists proposals(
  id text primary key, ts text, title text, reviewers text, ok integer,
  evidence text, imported_at text);
'''


def conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript(DDL)
    return c


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(65536), b''):
            h.update(b)
    return h.hexdigest()[:16]


def rid(*parts):
    return hashlib.sha1('|'.join(str(p) for p in parts).encode()).hexdigest()[:16]


def insert_run(c, **kw):
    kw.setdefault('imported_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    cols = ','.join(kw)
    ph = ','.join('?' * len(kw))
    c.execute('insert or replace into runs(%s) values(%s)' % (cols, ph), list(kw.values()))


def norm_ts(s):
    if not s:
        return None
    s = str(s).strip().replace('T', ' ')[:19]
    m = re.match(r'(\d{4})[-/]?(\d{2})[-/]?(\d{2})[ -]?(\d{2}):?(\d{2})', s)
    if m:
        return '%s-%s-%s %s:%s' % m.groups()
    return s


def import_json(c, path):
    '把一份评测 json 拆成若干 runs 行；不认识的结构记为 sysbench 并保留键名'
    try:
        d = json.load(open(path, encoding='utf-8'))
    except Exception as e:
        return 0
    h = sha(path)
    rel = os.path.relpath(path, WS)
    n = 0

    def one(o, kind, suite, subj=None):
        nonlocal n
        model = o.get('model') or subj or ''
        prov, _, name = model.partition('/') if '/' in model else ('', '', model)
        sc = o.get('score')
        mx = o.get('score_max')
        if sc is None:
            passes = [v for k, v in o.items() if re.fullmatch(r't\d+', k)]
            if passes:
                sc = sum(1 for v in passes if str(v).upper().startswith('PASS'))
                mx = len(passes)
        ts = norm_ts(o.get('ts') or '') or datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M')
        insert_run(c, id=rid(kind, model, ts, str(sc)), ts=ts, kind=kind,
                   suite=suite or o.get('mode') or '', provider=prov, model=name,
                   score=sc, score_max=mx, verdict=str(o.get('verdict') or o.get('note') or '')[:200],
                   latency_s=o.get('t1_s') or o.get('latency_s'), cost_cny=None,
                   evidence=rel, evidence_sha=h, note=json.dumps({k: v for k, v in o.items() if k in ('note', 't1', 't2', 'model_raw')}, ensure_ascii=False)[:400] or '')
        n += 1

    if isinstance(d, list):
        for o in d:
            if isinstance(o, dict):
                one(o, 'bench', os.path.basename(path))
    elif isinstance(d, dict):
        if 'model' in d:
            one(d, 'longctx' if 'longctx' in path else 'bench', os.path.basename(path))
        elif isinstance(d.get('results'), list):
            for o in d['results']:
                if isinstance(o, dict):
                    one(o, 'bench', os.path.basename(path))
        else:
            gpu = (d.get('gpu') or {}).get('name', '')
            subj = 'machine-A'
            insert_run(c, id=rid('sysbench', rel, subj), ts=datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M'),
                       kind='sysbench', suite=os.path.basename(path), provider='', model=subj,
                       score=None, score_max=None, verdict='基线', latency_s=None, cost_cny=None,
                       evidence=rel, evidence_sha=h, note=('keys=' + ','.join(list(d)[:12]) + (' gpu=' + gpu if gpu else ''))[:400])
            n += 1
    return n



CANON = [('GO-WITH-FIXES', ['go-with-fixes', 'go with fixes', '需修改后', '修改后上线', '补齐后可上线']),
         ('REJECT', ['reject', 'no-go', '不建议上线', '不建议', '不可上线', '不可执行', '驳回', '暂缓上线']),
         ('APPROVE', ['approve', 'go', '通过', '同意', '可上线']),
         ('WARNING', ['warning', '注意', '提醒'])]


def _canon(s):
    low = s.lower().replace('_', '-')
    for canon, keys in CANON:
        for k in keys:
            if k in low:
                return canon
    return 'UNKNOWN'


FAILDET = re.compile(r'timeout: failed to execute|took too long to respond|ECONNREFUSED|not authenticated|invalid_api_key|rate limit|quota|\b401\b', re.I)


def is_failed(txt):
    return bool(FAILDET.search(txt[:400])) and len(txt) < 800


def norm_verdict(txt):
    "显式 [VERDICT] 优先；否则定位最后一个「结论/判定/总结」段，按该段内最早出现的关键词判定"
    m = re.search(r'\[VERDICT\]\s*:?\s*\**\s*([A-Za-z_\-]+)', txt)
    if m:
        return _canon(m.group(1))
    cut = None
    for mm in re.finditer(r'(?:^|\n)[^\n]{0,12}(?:结论|判定|总结)[^\n]{0,12}\n', txt):
        cut = mm.end()
    seg = txt[cut:cut + 700] if cut else txt[:1200]
    low = seg.lower()
    best = None
    for canon, keys in CANON:
        for k in keys:
            i = low.find(k)
            if i >= 0 and (best is None or i < best[0]):
                best = (i, canon)
    return best[1] if best else 'UNKNOWN'


def import_reviews(c):
    'cross-review/<提案>/<评审员>.txt -> reviews 行'
    base = os.path.join(WS, 'state', 'work', 'cross-review')
    total = 0
    for d in sorted(glob.glob(os.path.join(base, '*'))):
        if not os.path.isdir(d):
            continue
        proposal = os.path.basename(d)
        for f in sorted(glob.glob(os.path.join(d, '*.txt'))):
            try:
                txt = open(f, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            prov = (re.search(r'^provider:\s*(\S+)', txt, re.M) or [None, ''])[1]
            model = (re.search(r'^model:\s*(\S+)', txt, re.M) or [None, ''])[1]
            verdict = 'FAILED' if is_failed(txt) else norm_verdict(txt)
            if not prov or not model:
                stem = os.path.basename(f).rsplit('.', 1)[0]
                if not model and stem.lower() not in ('minimax', 'zhipu', 'kimi', 'qianwen', 'zai', 'deepseek', 'glm'):
                    model = stem
                if not prov:
                    prov = stem.split('-')[0]
            ts = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M')
            c.execute('insert or replace into reviews(id,ts,proposal,provider,model,verdict,chars,evidence,evidence_sha,imported_at) values(?,?,?,?,?,?,?,?,?,?)',
                      (rid('review', os.path.relpath(f, WS), model, ts), ts, proposal, prov, model, verdict[:60], len(txt),
                       os.path.relpath(f, WS), sha(f), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            total += 1
    return total


def import_proposals(c):
    '交叉验证台账.md 的表格行 -> proposals'
    p = os.path.join(MODEL_WS, 'docs', '交叉验证台账.md')
    if not os.path.exists(p):
        return 0
    n = 0
    for ln in open(p, encoding='utf-8', errors='replace'):
        if not ln.startswith('|'):
            continue
        cells = [x.strip() for x in ln.strip().strip('|').split('|')]
        if len(cells) < 4 or not re.match(r'\d{4}-\d{2}-\d{2}', cells[0]):
            continue
        ts = norm_ts(cells[0])
        title = cells[1][:80]
        ok = 1 if ('2/2' in ' '.join(cells) and '全部完成' in ' '.join(cells)) else 0
        c.execute('insert or replace into proposals(id,ts,title,reviewers,ok,evidence,imported_at) values(?,?,?,?,?,?,?)',
                  (rid('prop', ts, title), ts, title, cells[2], ok, 'docs/交叉验证台账.md', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        n += 1
    return n


def import_model_ledger_md(c):
    '模型评测台账.md「历史评测」表（10-12/10-14 早期跑分只存在这里）'
    p = os.path.join(MODEL_WS, 'docs', '模型评测台账.md')
    if not os.path.exists(p):
        return 0
    n, inside = 0, False
    for ln in open(p, encoding='utf-8', errors='replace'):
        if ln.startswith('## 历史评测'):
            inside = True
            continue
        if inside and ln.startswith('## '):
            break
        if not inside or not ln.startswith('|'):
            continue
        cells = [x.strip() for x in ln.strip().strip('|').split('|')]
        if len(cells) < 5 or not re.match(r'\d{4}-\d{2}-\d{2}', cells[0]):
            continue
        model = cells[1]
        prov, _, name = model.partition('/')
        m = re.search(r'(\d+)\s*/\s*(\d+)', cells[2])
        sc, mx = (float(m.group(1)), float(m.group(2))) if m else (None, None)
        lat = re.search(r'([\d.]+)\s*s', cells[3])
        ts = norm_ts(cells[0]) or cells[0]
        insert_run(c, id=rid('bench', model, ts, str(sc)), ts=ts, kind='bench', suite='客观题',
                   provider=prov, model=name, score=sc, score_max=mx,
                   verdict=(cells[4] or '')[:120], latency_s=float(lat.group(1)) if lat else None,
                   cost_cny=None, evidence='workspace-model/docs/模型评测台账.md#历史评测',
                   evidence_sha=sha(p), note='md表格')
        n += 1
    return n


def import_bench_b_md(c):
    'workspace/state/work/model-bench-b.md：B 机本地模型吞吐表'
    p = os.path.join(WS, 'state', 'work', 'model-bench-b.md')
    if not os.path.exists(p):
        return 0
    txt = open(p, encoding='utf-8', errors='replace').read()
    mt = re.search(r'更新：([\d\-: ]+)', txt)
    ts = norm_ts(mt.group(1)) if mt else datetime.fromtimestamp(os.path.getmtime(p)).strftime('%Y-%m-%d %H:%M')
    n = 0
    for ln in txt.splitlines():
        if not ln.startswith('|'):
            continue
        cells = [x.strip() for x in ln.strip().strip('|').split('|')]
        if len(cells) < 6 or cells[0] in ('模型', '---') or cells[0].startswith('-'):
            continue
        name = cells[0]
        gen = re.search(r'([\d.]+)', cells[2])
        first = re.search(r'([\d.]+)\s*s', cells[5])
        note = '体积=%s 生成=%s tok/s 预填充=%s tok/s 显存=%s 视觉=%s %s' % (
            cells[1], cells[2], cells[3], cells[4], cells[6][:20], cells[7][:40] if len(cells) > 7 else '')
        insert_run(c, id=rid('bench', 'ollama/' + name, ts, 'tok'), ts=ts, kind='bench', suite='B机本地吞吐',
                   provider='ollama', model=name, score=float(gen.group(1)) if gen else None, score_max=None,
                   verdict='', latency_s=float(first.group(1)) if first else None, cost_cny=None,
                   evidence='state/work/model-bench-b.md', evidence_sha=sha(p), note=note[:300].strip())
        n += 1
    return n


def import_bench10(c):
    '模型管家 10 题 x 3 轮评测（workspace-model/state/model-warden/bench10-*.jsonl）→ 每模型一行均值'
    import glob, statistics as st
    fs = sorted(glob.glob(os.path.join(MODEL_WS, 'state', 'model-warden', 'bench10-*.jsonl')))
    n = 0
    for f in fs:
        day = re.search(r'bench10-(\d{8})', f)
        ts = '%s-%s-%s 20:00' % (day.group(1)[:4], day.group(1)[4:6], day.group(1)[6:]) if day else datetime.now().strftime('%Y-%m-%d %H:%M')
        by = {}
        for ln in open(f, encoding='utf-8', errors='replace'):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if not r.get('text', '').strip():
                by.setdefault(r['model'], []).append(None)
            else:
                by.setdefault(r['model'], []).append(r)
        for model, rows in by.items():
            ok = [x for x in rows if x]
            if not ok:
                continue
            sc = [x['score'] for x in ok]
            empt = len(rows) - len(ok)
            kd = {}
            for x in ok:
                kd.setdefault(x.get('kind', ''), []).append(x['score'])
            weak = sorted(kd.items(), key=lambda kv: st.mean(kv[1]))[:2]
            prov, _, name = model.partition('/')
            insert_run(c, id=rid('bench10', model, ts, '%.2f' % st.mean(sc)), ts=ts, kind='bench10',
                       suite='10题x3轮', provider=prov, model=name, score=round(st.mean(sc) * 10, 2), score_max=10,
                       verdict='空%d/%d' % (empt, len(rows)), latency_s=round(st.median([x['ms'] for x in ok]) / 1000, 1),
                       cost_cny=None, evidence=os.path.relpath(f, WS),
                       evidence_sha=sha(f), note='最弱题型: ' + ' / '.join('%s %.2f' % (k, st.mean(v)) for k, v in weak))
            n += 1
    return n


def stats(c):
    q = lambda s: c.execute(s).fetchall()
    print('runs       :', q('select count(*) from runs')[0][0])
    print('reviews    :', q('select count(*) from reviews')[0][0])
    print('proposals  :', q('select count(*) from proposals')[0][0])
    print('--- runs by kind ---')
    for k, n, lo, hi in q('select kind,count(*),min(ts),max(ts) from runs group by kind order by 2 desc'):
        print('  %-10s %4d  %s → %s' % (k, n, lo, hi))
    print('--- 被评测模型（前 10，按评测次数）---')
    for prov, model, n, lo, hi in q("select provider,model,count(*),min(ts),max(ts) from runs where model<>'' group by provider,model order by 3 desc limit 10"):
        print('  %-28s %3d  %s → %s' % ((prov + '/' + model).strip('/'), n, lo, hi))
    print('--- 评审员（前 10）---')
    for prov, model, n, lo, hi in q('select provider,model,count(*),min(ts),max(ts) from reviews group by provider,model order by 3 desc limit 10'):
        print('  %-28s %3d  %s → %s' % ((prov + '/' + model).strip('/'), n, lo, hi))
    print('--- 判定分布 ---')
    for v, n in q("select verdict,count(*) from reviews group by verdict order by 2 desc limit 8"):
        print('  %-24s %d' % (v[:24], n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['import', 'stats', 'list']); 
    ap.add_argument('--limit', type=int, default=20)
    a = ap.parse_args()
    c = conn()
    if a.cmd == 'import':
        rn = import_model_ledger_md(c) + import_bench_b_md(c) + import_bench10(c)
        for pat in ['state/eval/*.json', 'state/eval/history/*.json', 'state/bench/*.json']:
            for p in sorted(glob.glob(os.path.join(WS, pat))):
                rn += import_json(c, p)
        rv = import_reviews(c)
        pp = import_proposals(c)
        c.commit()
        print('导入：runs +%d，reviews +%d，proposals +%d' % (rn, rv, pp))
        stats(c)
    elif a.cmd == 'stats':
        stats(c)
    else:
        for row in c.execute('select ts,kind,provider,model,score,score_max,verdict,evidence from runs order by ts desc limit ?', (a.limit,)):
            print(' | '.join('' if x is None else str(x) for x in row))
    return 0


if __name__ == '__main__':
    sys.exit(main())
