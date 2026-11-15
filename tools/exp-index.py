#!/usr/bin/env python3
# exp-index.py - 汇总成功经验为可检索索引（worklog + 经验库 + 问题库 + 共享技能 + Windows 侧资产）
# 用法: python3 tools/exp-index.py [--quiet]
import json, os, re, sys, datetime, pathlib

WS = pathlib.Path('/home/j/.openclaw/workspace')
SKILLS = pathlib.Path('/home/j/.openclaw/shared-skills')
WIN_DIRS = ['/mnt/e/openclaw-tools', '/mnt/e/openclaw-store/desktop-tools', '/mnt/c/Users/J/Desktop']
OUT_MD = WS / 'docs' / ('成功经验索引-%s.md' % datetime.date.today().strftime('%Y%m%d'))
OUT_JSON = WS / 'state' / 'ledger' / 'exp-index.json'

RULES = [
    ('备份恢复', ['备份', '归档', '恢复', '镜像', '快照', 'backup', 'restore']),
    ('网关与重启', ['网关', 'gateway', '重启', 'restart', 'systemd', '看门狗', 'watchdog']),
    ('定时任务', ['cron', '定时', '排班', 'schedule']),
    ('Windows-WSL', ['wsl', 'vhdx', '互操作', 'interop', 'portproxy', '防火墙', '压缩']),
    ('节点与机器', ['节点', 'node', 'mypc', 'library', '配对', 'tls']),
    ('模型与额度', ['模型', 'deepseek', 'glm', 'kimi', 'ollama', '额度', '余额', '路由']),
    ('语音与视觉', ['语音', 'tts', 'voice', 'asr', '克隆', '人脸', 'face']),
    ('打印与3D', ['打印', 'printer', '3d', '拓竹', 'bambu', '3mf', 'makerworld']),
    ('媒体与存储', ['媒体', '库房', '去重', 'sha256', 'nas', '群晖']),
    ('手机与自动化', ['手机', 'adb', '淘宝', '短信', 'sms', 'kola']),
    ('飞书与渠道', ['飞书', 'feishu', '机器人', 'bot', '图标', 'scope']),
    ('账本与治理', ['账本', 'worklog', '自审', '议会', '评审', '技能', 'skill']),
]

def domain_of(*texts):
    blob = ' '.join(t for t in texts if t).lower()
    for name, keys in RULES:
        for k in keys:
            if k.lower() in blob:
                return name
    return '其他'

def load_worklog():
    out = []
    p = WS / 'state' / 'log' / 'worklog.jsonl'
    if not p.exists():
        return out
    keep = ('fix', 'deploy', 'change', 'incident', 'verify', 'decision')
    for line in p.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        cat = d.get('cat')
        if cat not in keep:
            continue
        summary = (d.get('summary') or '').strip()
        evidence = (d.get('evidence') or '').strip()
        detail = summary
        if evidence and evidence not in summary:
            detail = (summary + '｜证据：' + evidence).strip('｜')
        out.append({'source': 'worklog', 'date': (d.get('ts') or '')[:10],
                    'title': (d.get('target') or summary or '').strip(),
                    'detail': detail, 'rollback': (d.get('rollback') or '').strip(),
                    'cat': cat, 'domain': domain_of(d.get('target', ''), summary, evidence)})
    return out

def load_experience_doc():
    out = []
    p = WS / 'docs' / '经验库.md'
    if not p.exists():
        return out
    cur = None
    for line in p.read_text(encoding='utf-8').splitlines():
        m = re.match(r'^###\s+(.+)$', line)
        if m:
            cur = {'source': 'docs/经验库.md', 'date': '', 'title': m.group(1).strip(),
                   'detail': '', 'rollback': '', 'cat': 'experience'}
            out.append(cur)
        elif cur is not None and line.strip().startswith('-'):
            cur['detail'] = (cur['detail'] + ' ' + line.strip('- ').strip()).strip()
    for it in out:
        it['domain'] = domain_of(it['title'], it['detail'])
    return out

def load_problem_doc():
    out = []
    p = WS / 'docs' / '问题库.md'
    if not p.exists():
        return out
    for line in p.read_text(encoding='utf-8').splitlines():
        s = line.strip()
        if not s.startswith('-') or '🟢' not in s:
            continue
        txt = s.lstrip('- ').strip()
        title = txt.split('｜')[0].strip()
        out.append({'source': 'docs/问题库.md', 'date': '', 'title': title,
                    'detail': txt[len(title):].strip('｜ '), 'rollback': '',
                    'cat': 'problem-solved', 'domain': domain_of(txt)})
    return out

def load_skills():
    out = []
    if not SKILLS.exists():
        return out
    for d in sorted(SKILLS.iterdir()):
        f = d / 'SKILL.md'
        if not f.is_file():
            continue
        txt = f.read_text(encoding='utf-8', errors='replace')
        m = re.search(r'^description:\s*(.+)$', txt, re.M)
        desc = m.group(1).strip() if m else ''
        out.append({'source': 'shared-skills/' + d.name, 'date': '', 'title': d.name,
                    'detail': desc[:300], 'rollback': '', 'cat': 'skill',
                    'domain': domain_of(d.name, desc)})
    return out

def load_windows_assets():
    out = []
    for root in WIN_DIRS:
        try:
            names = sorted(os.listdir(root))
        except Exception:
            continue
        for n in names:
            low = n.lower()
            if not (low.endswith('.bat') or low.endswith('.log') or low.endswith('.ps1')):
                continue
            p = os.path.join(root, n)
            try:
                st = os.stat(p)
            except Exception:
                continue
            out.append({'source': p, 'date': datetime.date.fromtimestamp(st.st_mtime).isoformat(),
                        'title': n, 'detail': '%d 字节' % st.st_size, 'rollback': '',
                        'cat': 'windows-asset', 'domain': domain_of(n)})
    return out

def main():
    quiet = '--quiet' in sys.argv
    groups, stats = {}, {}
    for loader in (load_worklog, load_experience_doc, load_problem_doc, load_skills, load_windows_assets):
        rows = loader()
        stats[loader.__name__] = len(rows)
        for r in rows:
            groups.setdefault(r['domain'], []).append(r)

    order = [n for n, _ in RULES] + ['其他']
    lines = ['# 成功经验索引（%s）' % datetime.date.today(), '',
             '> 由 tools/exp-index.py 自动生成，勿手改；新增经验请写进统一账本或经验库后重跑。',
             '> 先查这里再动手：python3 tools/exp.py 关键词', '',
             '来源统计：' + '，'.join('%s %d' % (k, v) for k, v in stats.items()), '']
    total = 0
    for dom in order:
        rows = groups.get(dom)
        if not rows:
            continue
        lines.append('## %s（%d）' % (dom, len(rows)))
        lines.append('')
        seen = set()
        for r in sorted(rows, key=lambda x: x['date'], reverse=True):
            key = (r['title'], r['detail'][:60])
            if key in seen:
                continue
            seen.add(key)
            total += 1
            head = '- [%s] %s' % (r['cat'], r['title'])
            if r['date']:
                head += '（%s）' % r['date']
            lines.append(head)
            if r['detail']:
                lines.append('  - ' + r['detail'].replace('\n', ' ')[:400])
            if r['rollback']:
                lines.append('  - 回滚：' + r['rollback'][:200].replace('\n', ' '))
            lines.append('  - 来源：' + r['source'])
        lines.append('')

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    OUT_JSON.write_text(json.dumps({'generated': datetime.datetime.now().isoformat(timespec='seconds'),
                                    'stats': stats, 'items': [i for v in groups.values() for i in v]},
                                   ensure_ascii=False), encoding='utf-8')
    if not quiet:
        print('索引已生成：%s（%d 条 / %d 个领域）' % (OUT_MD, total, len(groups)))
        for k, v in stats.items():
            print('  %s: %d' % (k, v))

if __name__ == '__main__':
    main()
