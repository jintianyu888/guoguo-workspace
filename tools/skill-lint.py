#!/usr/bin/env python3
"""skill-lint.py —— 技能静态体检（零 token）

查的是「技能还管不管用」的结构性证据，不是文风：
  1. frontmatter 的 name 与目录名一致、description >= 20 字
  2. 三件套齐全：什么时候用 / 步骤 / 验证
  3. 正文引用的绝对路径、工具脚本是否还存在（技能最常腐烂的地方）
  4. 是否有回滚说明、篇幅是否过薄

用法：
  python3 tools/skill-lint.py [--json] [--fix]
--fix 只做机械修复：给缺 version/updated 的补一行，不碰正文。
"""
import json, os, re, sys, time

W = '/home/j/.openclaw/workspace'
SHARED = '/home/j/.openclaw/shared-skills'
BT = chr(96)

# 硬错误只有客观项：frontmatter/命名/摘要长度/引用失效
# 结构项（步骤、验证、触发、回滚）只提示——不同技能的写法差异太大，硬判会误杀
REQ = {}
SOFT = {
    'steps': ['步骤', 'Steps', 'Procedure', '流程', '用法', 'Usage', 'How to', 'Scan', 'Handle'],
    'verify': ['验证', 'Verify', 'Verification', '完成检查', 'Completion check', '自检'],
    'when': ['什么时候用', '何时使用', 'When to use', 'When To Use', '触发', 'Activate when'],
    'rollback': ['回滚', 'Rollback', '撤销'],
}


def read(p):
    try:
        return open(p, encoding='utf-8').read()
    except Exception:
        return ''


def frontmatter(txt):
    if not txt.startswith('---'):
        return {}
    end = txt.find(chr(10) + '---', 3)
    if end < 0:
        return {}
    fm = {}
    for line in txt[3:end].splitlines():
        if ':' in line and not line.strip().startswith('#'):
            k, v = line.split(':', 1)
            fm[k.strip().lower()] = v.strip()
    return fm


def collect_refs(txt):
    paths = set(re.findall(r'(?:/home/j|/mnt)/[A-Za-z0-9._~/\-]+', txt))
    tools = set(re.findall(r'\btools/[A-Za-z0-9._\-]+\.(?:py|sh)', txt))
    clean = set()
    for p in paths:
        if '...' in p or '*' in p or p.endswith('/'):
            continue
        clean.add(p.rstrip('.,)-').rstrip('/'))
    return clean, tools


def check(name, path):
    txt = read(path)
    fm = frontmatter(txt)
    errs, warns = [], []
    if not fm:
        errs.append('缺 frontmatter（name/description）')
    else:
        if fm.get('name') and fm['name'] != name:
            errs.append('name=%s 与目录名不符' % fm['name'])
        d = fm.get('description', '')
        if len(d) < 20:
            errs.append('description 太短（%d 字），触发不准' % len(d))
    low = txt.lower()
    heads = re.findall(r'^#{1,4}\s*(.+)$', txt, re.M)
    numbered = [h for h in heads if re.match(r'^\d+[.、)]', h.strip())]
    for k, alts in SOFT.items():
        hit = any(a.lower() in low for a in alts)
        if not hit and k == 'steps' and len(numbered) >= 2:
            hit = True   # 「## 1. xxx / ## 2. yyy」也算步骤
        if not hit:
            label = {'steps': '步骤', 'verify': '验证', 'when': '触发场景', 'rollback': '回滚'}[k]
            warns.append('缺%s节' % label)
    paths, tools = collect_refs(txt)
    # 允许显式豁免：<!-- allow-missing: /path/a /path/b -->
    allow = set()
    for m in re.findall(r'allow-missing:(.*?)-->', txt, re.S):
        allow.update(m.split())
    for p in sorted(paths - allow):
        if not os.path.exists(p):
            errs.append('引用路径不存在：%s' % p)
    for t in sorted(tools):
        if not os.path.exists(os.path.join(W, t)):
            errs.append('引用工具不存在：%s' % t)
    lines = len(txt.splitlines())
    if lines < 12:
        warns.append('篇幅过薄（%d 行）' % lines)
    if not fm.get('version'):
        warns.append('无 version 字段')
    return {'skill': name, 'path': path, 'lines': lines,
            'errors': errs, 'warnings': warns}


def fix(name, path):
    txt = read(path)
    fm = frontmatter(txt)
    if not fm or fm.get('version'):
        return False
    stamp = time.strftime('%Y-%m-%d')
    head = txt.split(chr(10) + '---', 1)
    if len(head) != 2:
        return False
    new = head[0] + chr(10) + 'version: 1' + chr(10) + 'updated: ' + stamp + chr(10) + '---' + head[1]
    open(path, 'w', encoding='utf-8').write(new)
    return True


def main():
    args = sys.argv[1:]
    as_json = '--json' in args
    do_fix = '--fix' in args
    rows = []
    for name in sorted(os.listdir(SHARED)):
        p = os.path.join(SHARED, name, 'SKILL.md')
        if not os.path.isfile(p) or name.startswith('.'):
            continue
        if do_fix and fix(name, p):
            rows.append({'skill': name, 'fixed': 'version'})
        rows.append(check(name, p))
    rows = [r for r in rows if 'errors' in r]
    bad = [r for r in rows if r['errors']]
    warned = [r for r in rows if r['warnings'] and not r['errors']]
    if as_json:
        print(json.dumps({'total': len(rows), 'errors': bad, 'warnings': warned},
                         ensure_ascii=False, indent=1))
    else:
        print('技能体检 %s：%d 个，错误 %d，提示 %d' % (
            time.strftime('%Y-%m-%d'), len(rows), len(bad), len(warned)))
        for r in bad:
            print('  ❌ %s' % r['skill'])
            for e in r['errors']:
                print('     - %s' % e)
        for r in warned:
            print('  ⚠ %s：%s' % (r['skill'], '；'.join(r['warnings'])))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
