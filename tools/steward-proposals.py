#!/usr/bin/env python3
"""steward-proposals.py —— 四大管家建议台账（唯一真源 proposals.jsonl）

用法:
  ingest [--days N]     扫描管家报告，抽取建议，去重入库（重提计数+1）
  list [--status S] [--domain D]
  set ID STATUS [--note TEXT]   STATUS: new/approved/rejected/deferred/done
  digest                生成每日摘要（新增/超期/重提/待批）
约定：只有 main 能 set approved；提案与批准分离。
"""
import json, os, re, sys, hashlib, time, datetime

WS = '/home/j/.openclaw/workspace'
LED = os.path.join(WS, 'state/approvals/proposals.jsonl')
SCAN = [
    ('maint', ['/home/j/openclaw-workspaces/maint']),
    ('backup', ['/home/j/.openclaw/workspace-backup']),
    ('model', ['/home/j/.openclaw/workspace-model']),
    ('work', ['/home/j/openclaw-workspaces/work']),
]
LVL = re.compile(r'\bP([012])\b')

def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def load():
    out = []
    if os.path.exists(LED):
        for line in open(LED, encoding='utf-8'):
            line = line.strip()
            if line:
                try: out.append(json.loads(line))
                except Exception: pass
    return out

def save(items):
    os.makedirs(os.path.dirname(LED), exist_ok=True)
    tmp = LED + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')
    os.replace(tmp, LED)

def norm(text):
    t = re.sub(r'[0-9a-f]{8,}', '', text)
    t = re.sub(r'\s+', ' ', t).strip().lower()[:60]
    t = re.sub(r'[0-9a-f]{8,}', '', t)
    return hashlib.sha1(t.encode('utf-8')).hexdigest()[:16]

NOISE_RULES = [
    ('no-p0', r'无\s*P0|没有\s*P0|无 ?P0 ?问题'),
    ('stats', r'(结论|合计|汇总|本次结论)\s*[:：]?.{0,30}?\d+\s*条'),
    ('fragment', r'^(归属|后果|判定|背景|说明)\s*[:：]'),
    ('fixed', r'已修(复|好)?[^。]{0,220}(闭单|已解决)'),
]

def is_noise(text):
    """发布前审查：返回噪声类型，'' 表示可发布。"""
    t = (text or '').strip()
    if not t:
        return 'empty'
    for name, pat in NOISE_RULES:
        if not re.search(pat, t):
            continue
        if name == 'fragment' and (re.search(r'\.[a-z]{2,4}:\d+', t) and len(t) > 120):
            continue
        if name == 'fragment' and re.search(r'复发|仍在|未修|仍未', t):
            continue          # 带状态更新的碎片保留，别丢信息
        if name == 'fixed' and re.search(r'但|仍(在|未)', t):
            continue          # “已修A但B仍在”是真问题
        return name
    return ''

def parse_file(path, domain):
    rows = []
    try:
        txt = open(path, encoding='utf-8', errors='replace').read()
    except Exception:
        return rows
    for i, line in enumerate(txt.splitlines(), 1):
        s = line.strip()
        if not s.startswith(('-', '*')): continue
        body = s.lstrip('-* ').strip()
        if len(body) < 8: continue
        m = LVL.search(body[:40])
        has_file = bool(re.search(r'[\w./-]+\.(sh|py|md|json|js|sqlite|db):\d+|\.[a-z]+:[0-9]+', body))
        if not (m or has_file): continue
        if any(k in body for k in ('默认批准','默认不批准','定义见')): continue
        if not (m or '建议' in body or '必须' in body): continue
        rows.append({
            'lvl': ('P' + m.group(1)) if m else 'P2',
            'text': body[:400],
            'file_hint': (re.search(r'([\w./-]+\.(?:sh|py|md|json|js|sqlite|db)):\d+', body) or [None])[0] if re.search(r'([\w./-]+\.(?:sh|py|md|json|js|sqlite|db)):\d+', body) else '',
            'src': f'{path}:{i}',
        })
    return rows

def cmd_ingest(days):
    items = load(); idx = {it['id']: it for it in items}
    seen = {it['norm']: it for it in items}
    cutoff = time.time() - days * 86400
    added = dup = 0
    for domain, roots in SCAN:
        for root in roots:
            for dp, _, fns in os.walk(root):
                if '/.git' in dp or '/node_modules' in dp or '/state/tmp' in dp: continue
                for fn in fns:
                    if not fn.endswith('.md'): continue
                    p = os.path.join(dp, fn)
                    try:
                        if os.path.getmtime(p) < cutoff: continue
                    except OSError: continue
                    for row in parse_file(p, domain):
                        if is_noise(row['text']):
                            continue
                        key = norm(row['text'])
                        if key in seen:
                            it = seen[key]
                            if it.get('last_src') != row['src']:
                                it['repeats'] = it.get('repeats', 1) + 1
                                it['last_seen'] = now()
                                it['last_src'] = row['src']
                                dup += 1
                            continue
                        it = {
                            'id': 'S' + str(len(items) + 1).zfill(4),
                            'norm': key, 'domain': domain, 'lvl': row['lvl'],
                            'text': row['text'], 'file_hint': row['file_hint'],
                            'src': row['src'], 'last_src': row['src'],
                            'status': 'new', 'first_seen': now(), 'last_seen': now(),
                            'repeats': 1, 'note': ''
                        }
                        items.append(it); idx[it['id']] = it; seen[key] = it; added += 1
    save(items)
    print(f'新增 {added} 条，重提 {dup} 条，台账共 {len(items)} 条 → {LED}')

def cmd_list(status=None, domain=None):
    for it in load():
        if status and it['status'] != status: continue
        if domain and it['domain'] != domain: continue
        print(it['id'], it['lvl'], it['domain'], it['status'], f"x{it.get('repeats',1)}", it['text'][:110])

def cmd_set(i, status, note=''):
    items = load(); hit = False
    for it in items:
        if it['id'] == i:
            it['status'] = status
            it['note'] = note or it.get('note', '')
            it['updated'] = now()
            hit = True
    if not hit:
        print('未找到', i); return 1
    save(items); print(f'{i} -> {status}'); return 0

def cmd_clean(dry=False):
    items = load(); n = 0; detail = []
    for it in items:
        if it.get('status') not in ('new', 'deferred'):
            continue
        why = is_noise(it.get('text', ''))
        if not why:
            continue
        it['status'] = 'done' if why == 'fixed' else 'rejected'
        note = (it.get('note') or '').strip()
        it['note'] = (note + ' | ' if note else '') + f'发布前审查:{why} {now()}'
        n += 1; detail.append(f"{it['id']} {it['lvl']} {why} {it['text'][:60]}")
    if n and not dry:
        save(items)
    print(f'发布前审查处置 {n} 条' + ('（dry-run，未落盘）' if dry else ''))
    for d in detail:
        print('  -', d)
    return 0

def age_h(it):
    try:
        t = datetime.datetime.strptime(it['first_seen'], '%Y-%m-%d %H:%M:%S')
        return (datetime.datetime.now() - t).total_seconds() / 3600
    except Exception:
        return 0.0

def cmd_digest():
    items = load()
    openi = [i for i in items if i['status'] in ('new', 'deferred')]
    p0 = [i for i in openi if i['lvl'] == 'P0']
    over = [i for i in openi if (i['lvl'] == 'P0' and age_h(i) > 48) or (i['lvl'] == 'P1' and age_h(i) > 168)]
    rep = [i for i in openi if i.get('repeats', 1) >= 3]
    if not items:
        print(''); return
    print(f'【管家建议台账 {now()}】未结 {len(openi)} 条（P0 {len(p0)}）· 超期 {len(over)} · 重提≥3 {len(rep)}')
    for i in over[:8]:
        print(f"  ⏰ {i['id']} {i['lvl']} {i['domain']} 已挂 {int(age_h(i))}h: {i['text'][:80]}")
    for i in rep[:8]:
        print(f"  🔁 {i['id']} {i['lvl']} {i['domain']} 重提 {i['repeats']} 次: {i['text'][:80]}")

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(0)
    if a[0] == 'ingest':
        d = int(a[a.index('--days') + 1]) if '--days' in a else 3
        cmd_ingest(d)
    elif a[0] == 'list':
        st = a[a.index('--status') + 1] if '--status' in a else None
        dm = a[a.index('--domain') + 1] if '--domain' in a else None
        cmd_list(st, dm)
    elif a[0] == 'set':
        sys.exit(cmd_set(a[1], a[2], a[a.index('--note') + 1] if '--note' in a else ''))
    elif a[0] == 'clean':
        sys.exit(cmd_clean('--dry' in a))
    elif a[0] == 'digest':
        cmd_digest()
    else:
        print(__doc__)
