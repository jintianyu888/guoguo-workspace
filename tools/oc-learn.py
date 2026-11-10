#!/usr/bin/env python3
"""oc-learn.py — 上游学习：从 OpenClaw GitHub / 官方文档 / ClawHub 抓新变化，
对照本机实况产出候选优化建议。零 token、只读、绝不自动改配置。

用法:
  run [--days N]   抓取并分析，写 digest + 候选（默认 14 天窗口）
  digest           只看最新一期摘要
  --ingest         把候选写进 state/approvals/proposals.jsonl（默认只落 digest）
数据: state/oc-learn/{releases.json,seen.json,digest-YYYYMMDD.md}
安全: 只发 GET 到白名单域名；不执行任何上游文本；建议一律 status=new 待人/双审。
"""
import json, os, re, sys, time, hashlib, datetime, urllib.request
CHR = chr(10)

WS = '/home/j/.openclaw/workspace'
DIR = os.path.join(WS, 'state/oc-learn')
LED = os.path.join(WS, 'state/approvals/proposals.jsonl')
ALLOW = ('api.github.com', 'raw.githubusercontent.com', 'docs.openclaw.ai', 'clawhub.ai')
UA = {'User-Agent': 'guoguo-oc-learn/1.0'}

# 与我们这台机器真正相关的关键词 -> 影响面判定
KEYS = {
    'upgrade':    ['upgrade', 'migration', 'schema', 'breaking', 'deprecat', 'rollback'],
    'cron':       ['cron', 'schedul', 'timer', 'job'],
    'memory':     ['memory', 'embed', 'lancedb', 'recall', 'compaction'],
    'channel':    ['feishu', 'lark', 'telegram', 'channel', 'webhook'],
    'security':   ['security', 'cve', 'auth', 'token', 'permission', 'ssrf'],
    'perf':       ['performance', 'memory leak', 'slow', 'latency', 'sqlite', 'wal'],
    'plugin':     ['plugin', 'skill', 'extension'],
    'model':      ['model', 'provider', 'fallback', 'stream'],
}

def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def get(url, timeout=25):
    host = url.split('/')[2]
    if host not in ALLOW:
        raise SystemExit('域名不在白名单: ' + host)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')

def load_json(p, default):
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception:
        return default

def save_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    json.dump(obj, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, p)

def local_version():
    try:
        for line in os.popen('openclaw --version 2>/dev/null').read().splitlines():
            m = re.search(r'(\d{4}\.\d+\.\d+)', line)
            if m:
                return m.group(1), line.strip()
    except Exception:
        pass
    return None, ''


def vkey(tag):
    m = re.search(r'(\d{4})\.(\d+)\.(\d+)', tag or '')
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

def classify(body):
    low = body.lower()
    hits = []
    for dom, kws in KEYS.items():
        if any(k in low for k in kws):
            hits.append(dom)
    return hits

def severity(rel, hits, ours):
    """粗判等级：涉及升级/破坏性变更且我们落后 -> P1；其余 P2。"""
    body = (rel.get('body') or '').lower()
    name = rel.get('tag_name') or rel.get('name') or ''
    if 'upgrade' in hits and any(w in body for w in ('breaking', 'migration', 'schema')):
        return 'P1'
    if 'security' in hits and ours and name and name != ours:
        return 'P1'
    return 'P2'

def fetch_releases(days):
    since = time.time() - days * 86400
    raw = get('https://api.github.com/repos/openclaw/openclaw/releases?per_page=30')
    data = json.loads(raw)
    out = []
    for rel in data:
        pub = rel.get('published_at') or ''
        try:
            ts = datetime.datetime.strptime(pub[:19], '%Y-%m-%dT%H:%M:%S').timestamp()
        except Exception:
            ts = 0
        if ts and ts < since:
            continue
        out.append({
            'tag': rel.get('tag_name') or rel.get('name'),
            'published': pub,
            'url': rel.get('html_url'),
            'body': (rel.get('body') or '')[:8000],
        })
    return out


# ---- 能力缺口：文档里有的、我们配置/工具里没碰过的 ----------------
CAPS = {
    'voice/语音回复':      ['voice', 'tts', 'speech'],
    'sandbox/沙箱':        ['sandbox'],
    'tailscale/funnel':    ['tailscale', 'funnel'],
    'webhook':             ['webhook'],
    'hooks/生命周期钩子':  ['hooks'],
    'memory.search':       ['memory.search', 'memory_search', 'search-enable', 'semantic', '"search"'],
    'workflows/工作流':     ['workflow'],
    'canvas/面板':         ['canvas'],
    'portal/端口暴露':     ['portal'],
    'computer/桌面控制':   ['computer'],
    'browser/浏览器':      ['browser'],
    'embeddings/向量':     ['embed'],
    'budget/成本预算':     ['budget', 'cost'],
    'audit/审计':          ['audit'],
    'redaction/脱敏':      ['redact'],
    'retention/保留策略':  ['retention', 'retain'],
    'subagents/子代理':    ['subagent', 'sessions_spawn'],
    'skills/技能库':       ['skill'],
    'plugins/插件':        ['plugin'],
}

def capability_gaps():
    """看本机配置+工具名里有没有用到这类能力，没用到就列出来给人看。"""
    blob = []
    for f in ('/home/j/.openclaw/openclaw.json',):
        try:
            blob.append(open(f, encoding='utf-8', errors='replace').read().lower())
        except Exception:
            pass
    for d in (os.path.join(WS, 'tools'), os.path.join(WS, 'state'), os.path.join(WS, 'docs')):
        try:
            blob.append(' '.join(os.listdir(d)).lower())
        except Exception:
            pass
    for f in (os.path.join(WS, 'AGENTS.md'), '/home/j/.config/feishu-alert-webhook'):
        try:
            blob.append(open(f, encoding='utf-8', errors='replace').read().lower())
        except Exception:
            pass
    text = ' '.join(blob)
    gaps = []
    for name, kws in CAPS.items():
        if not any(k.lower() in text for k in kws):
            gaps.append(name)
    return gaps

def main():
    args = sys.argv[1:]
    cmd = args[0] if args else 'run'
    days = 14
    for i, a in enumerate(args):
        if a == '--days' and i + 1 < len(args):
            days = int(args[i + 1])
    os.makedirs(DIR, exist_ok=True)
    relp = os.path.join(DIR, 'releases.json')
    seenp = os.path.join(DIR, 'seen.json')

    if cmd == 'digest':
        files = sorted([f for f in os.listdir(DIR) if f.startswith('digest-')])
        if not files:
            print('还没有任何 digest，先跑 run')
            return 0
        print(open(os.path.join(DIR, files[-1]), encoding='utf-8').read())
        return 0

    ours, verline = local_version()
    seen = load_json(seenp, {})
    releases = fetch_releases(days)
    save_json(relp, releases)

    fresh = [r for r in releases if seen.get(r['tag'], {}).get('sha') != hashlib.sha1((r['body'] or '').encode()).hexdigest()[:12]]
    cands = []
    for rel in releases:
        hits = classify(rel['body'])
        if not hits:
            continue
        lvl = severity(rel, hits, ours)
        # 只给新版本里的变化出建议，老版本记着看过就行
        if rel['tag'] not in [f['tag'] for f in fresh]:
            continue
        if ours and vkey(rel['tag']) <= vkey(ours):
            continue
        head = (rel['body'] or '').strip().split('\n')
        points = [ln.strip(' -*)') for ln in head if ln.strip().startswith(('-', '*'))][:4]
        cands.append({
            'tag': rel['tag'],
            'level': lvl,
            'domains': hits,
            'url': rel['url'],
            'points': points,
        })

    for r in releases:
        seen[r['tag']] = {'sha': hashlib.sha1((r['body'] or '').encode()).hexdigest()[:12], 'seen': now()}
    save_json(seenp, seen)

    today = datetime.datetime.now().strftime('%Y%m%d')
    lines = ['# 上游学习 · ' + now(), '',
             '本机版本: ' + (verline or '未取到'), '窗口: 近 %d 天 | 抓到 release %d 条 | 新变化 %d 条' % (days, len(releases), len(fresh)), '']
    newer = [r['tag'] for r in fresh if ours and vkey(r['tag']) > vkey(ours)]
    if ours and not newer:
        lines.append('本机 %s 已是最新，无新版本可升。' % ours)
    if not cands:
        lines.append('本期没有需要动作的上游变化。')
    for c in cands:
        lines.append('## [%s] %s  (%s)' % (c['level'], c['tag'], ','.join(c['domains'])))
        lines.append('来源: ' + (c['url'] or '-'))
        for p in c['points']:
            lines.append('- ' + p)
        lines.append('')
    gaps = capability_gaps()
    lines.append('')
    lines.append('## 能力缺口（文档有、本机配置/工具没用到）')
    if gaps:
        for g in gaps:
            lines.append('- ' + g)
    else:
        lines.append('无。')
    lines.append('')
    dp = os.path.join(DIR, 'digest-%s.md' % today)
    open(dp, 'w', encoding='utf-8').write('\n'.join(lines))
    print('\n'.join(lines[:20]))
    print('...')
    print('digest: ' + dp)

    if '--ingest' in args and cands:
        old = []
        if os.path.exists(LED):
            for line in open(LED, encoding='utf-8'):
                line = line.strip()
                if line:
                    try:
                        old.append(json.loads(line))
                    except Exception:
                        pass
        known = {o.get('norm') for o in old}
        added = 0
        for c in cands:
            title = '上游 %s 变化：%s' % (c['tag'], '；'.join(c['points'][:2]) if c['points'] else '见 digest')
            norm = hashlib.sha1(title.encode()).hexdigest()[:16]
            if norm in known:
                continue
            old.append({
                'id': 'L%s' % norm[:8], 'lvl': c['level'], 'text': title, 'norm': norm,
                'domain': c['domains'][0], 'src': 'oc-learn:' + c['tag'], 'last_src': c['url'] or '',
                'status': 'new', 'first_seen': now(), 'last_seen': now(), 'repeats': 1, 'note': '',
            })
            known.add(norm)
            added += 1
        tmp = LED + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            for it in old:
                f.write(json.dumps(it, ensure_ascii=False) + '\n')
        os.replace(tmp, LED)
        print('已入库候选: %d 条（status=new，需人工/双审才能落地）' % added)
        if added and '--notify' in args:
            msg = ('上游学习：发现 %d 条与本机相关的新变化（P1 %d 条）' % (
                added, sum(1 for c in cands if c['level'] == 'P1'))
                + CHR + CHR.join('- [%s] %s' % (c['level'], c['tag']) for c in cands[:5])
                + CHR + '看 ' + dp)
            try:
                import subprocess
                subprocess.run(['bash', os.path.join(WS, 'tools/notify.sh'), msg], timeout=60)
            except Exception as e:
                print('notify 失败: %s' % e)
    return 0

if __name__ == '__main__':
    sys.exit(main())
