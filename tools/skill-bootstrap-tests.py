#!/usr/bin/env python3
"""skill-bootstrap-tests.py —— 给还没有 selftest.sh 的技能生成通用自检（零 token）

通用自检只验「技能引用的脚本还在、还能解析」——这是技能腐烂最高频的原因。
有专属 selftest.sh 的不覆盖；生成的文件带标记，可随时替换成真测试。

用法：python3 tools/skill-bootstrap-tests.py [--dry]
"""
import os, re, sys

W = '/home/j/.openclaw/workspace'
SHARED = '/home/j/.openclaw/shared-skills'
D = '$'

TPL = '''#!/usr/bin/env bash
# 自动生成：skill-bootstrap-tests.py（通用自检——引用脚本存在且可解析）
# 想加强：直接改写本文件，maintain 不会覆盖已存在的 selftest.sh
set -u
W=/home/j/.openclaw/workspace
fail=0
for f in %s; do
  if [ ! -f "%sW/$f" ]; then echo "缺 $f"; fail=1; continue; fi
  case "$f" in
    *.py) python3 -c "import ast,sys;ast.parse(open('%sW/$f',encoding='utf-8').read())" 2>/dev/null || { echo "语法错 $f"; fail=1; } ;;
  esac
done
[ "$fail" -eq 0 ] && echo "refs ok"
exit "$fail"
'''


def main():
    dry = '--dry' in sys.argv[1:]
    made = []
    for name in sorted(os.listdir(SHARED)):
        d = os.path.join(SHARED, name)
        if name.startswith('.') or not os.path.isdir(d):
            continue
        st = os.path.join(d, 'selftest.sh')
        if os.path.exists(st):
            continue
        md = os.path.join(d, 'SKILL.md')
        if not os.path.isfile(md):
            continue
        txt = open(md, encoding='utf-8').read()
        refs = sorted(set(re.findall(r'\btools/[A-Za-z0-9._\-]+\.(?:py|sh)', txt)))
        refs = [r for r in refs if os.path.exists(os.path.join(W, r))]
        if not refs:
            continue
        body = TPL % (' '.join('"%s"' % r for r in refs), D, D)
        if dry:
            made.append((name, refs))
            continue
        open(st, 'w', encoding='utf-8').write(body)
        os.chmod(st, 0o755)
        made.append((name, refs))
    print('生成 %d 个通用自检' % len(made))
    for n, r in made:
        print('  - %s（%d 个引用）' % (n, len(r)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
