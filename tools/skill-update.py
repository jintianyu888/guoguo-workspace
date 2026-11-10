#!/usr/bin/env python3
"""skill-update.py —— 技能自我优化（用完就改，改完留版本）

2026-11-10 主公令：每次用技能踩了坑，当场把它写回技能里，下次不再踩。
用法：
  python3 tools/skill-update.py <技能名> "<一句话补充>" [--section 坑|步骤|验证|注意|前置]
  python3 tools/skill-update.py --history <技能名>

效果：追加一条带日期的条目 → 版本号 +1 → 旧版本存档到 .history/ → 校验结构
"""
import os, re, shutil, sys, time

SHARED = '/home/j/.openclaw/shared-skills'
HIST = os.path.join(SHARED, '.history')
SEC_MAP = {'坑': '## 坑与注意', '注意': '## 坑与注意', '步骤': '## 步骤',
           '验证': '## 验证', '前置': '## 前置条件 / 环境'}


def die(msg, code=2):
    print(msg); sys.exit(code)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); return 2
    if args[0] == '--history':
        name = args[1] if len(args) > 1 else ''
        d = os.path.join(HIST, name)
        if not os.path.isdir(d):
            print('无历史版本')
            return 0
        for f in sorted(os.listdir(d)):
            print(f)
        return 0

    name = args[0]
    text = ''
    section = '## 坑与注意'
    i = 1
    while i < len(args):
        a = args[i]
        if a == '--section' and i + 1 < len(args):
            section = SEC_MAP.get(args[i + 1], args[i + 1]); i += 2; continue
        text = (text + ' ' + a).strip(); i += 1
    if not text:
        die('缺少要补充的内容')

    path = os.path.join(SHARED, name, 'SKILL.md')
    if not os.path.exists(path):
        die('技能不存在：' + name)

    src = open(path, encoding='utf-8').read()
    today = time.strftime('%Y-%m-%d')

    # 1) 版本 +1（没有就补）
    m = re.search(r'^version:\s*(\d+)$', src, re.M)
    ver = int(m.group(1)) + 1 if m else 2
    if m:
        src = re.sub(r'^version:\s*\d+$', 'version: %d' % ver, src, count=1, flags=re.M)
    else:
        src = src.replace('---' + chr(10), '---' + chr(10) + 'version: %d' % ver + chr(10), 1)
    if re.search(r'^updated:', src, re.M):
        src = re.sub(r'^updated:.*$', 'updated: ' + today, src, count=1, flags=re.M)
    else:
        src = src.replace('version: %d' % ver, 'version: %d' % ver + chr(10) + 'updated: ' + today, 1)

    # 2) 追加条目到指定小节末尾
    entry = '- %s：%s' % (today, text)
    if section not in src:
        src = src.rstrip() + chr(10) + chr(10) + section + chr(10) + chr(10) + entry + chr(10)
    else:
        start = src.index(section)
        nxt = src.find(chr(10) + '## ', start + 1)
        end = nxt if nxt != -1 else len(src)
        block = src[start:end].rstrip()
        src = src[:start] + block + chr(10) + entry + chr(10) + (src[end:] if nxt != -1 else '')

    # 3) 存档旧版
    hd = os.path.join(HIST, name)
    os.makedirs(hd, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    shutil.copy(path, os.path.join(hd, 'v%d-%s.md' % (ver - 1, stamp)))

    open(path, 'w', encoding='utf-8').write(src)

    # 4) 校验
    checks = [('name:', 'name'), ('description:', 'description'),
              ('## 什么时候用', '什么时候用'), (section, section)]
    missing = [lab for pat, lab in checks if pat not in src]
    if missing:
        die('❌ 校验失败，缺：' + ', '.join(missing), 3)
    # 5) 镜像到 main 实际加载的 workshop 副本，防止共享主本更新后加载的仍是旧版
    try:
        import subprocess
        subprocess.run(['bash', '/home/j/.openclaw/workspace/tools/skill-mirror.sh'],
                       capture_output=True, timeout=30)
    except Exception:
        pass
    print('✅ %s → v%d（%s 追加 1 条），旧版存 .history/%s/' % (name, ver, section, name))
    print('   如果这条是新领域的做法，顺手把 description 或步骤也改一下')
    return 0


if __name__ == '__main__':
    sys.exit(main())
