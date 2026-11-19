#!/usr/bin/env python3
"""audit-scripts.py v2 - 脚本定时自查：语法/路径/冲突/安全/遗漏/优化（零 token）"""
import os, re, glob, subprocess, datetime, collections, json
W = '/home/j/.openclaw/workspace'
out, issues = [], 0
def p(s): out.append(s)
def issue(s):
    global issues
    issues += 1
    p(s)
p('# 脚本自查报告  ' + datetime.datetime.now().strftime('%F %T'))
sh_files = sorted(glob.glob(W + '/tools/*.sh'))
py_files = sorted(glob.glob(W + '/tools/*.py'))
p('')
p('## 1) Shell 语法（%d）' % len(sh_files))
bash_only = []
for f in sh_files:
    if subprocess.run(['sh','-n',f], capture_output=True).returncode != 0:
        if subprocess.run(['bash','-n',f], capture_output=True).returncode != 0: issue('- 语法错（sh+bash 都错）：' + os.path.basename(f))
        else: bash_only.append(os.path.basename(f))
p('- 仅 bash 语法（无人用 sh 调用则无害）：' + ', '.join(bash_only) if bash_only else '- 全部 sh 兼容')
p('')
p('## 2) Python 语法（%d）' % len(py_files))
for f in py_files:
    if subprocess.run(['python3','-c','import ast,sys;ast.parse(open(sys.argv[1]).read())',f], capture_output=True).returncode != 0: issue('- 语法错：' + os.path.basename(f))
p('- 检查完毕')
p('')
p('## 3) 冲突检测：多脚本写同一文件')
writes = collections.defaultdict(set)
for f in sh_files + py_files:
    try: t = open(f, errors='ignore').read()
    except Exception: continue
    for m in re.findall(r'(?:>>?|tee\s+)\s*["\x27]?(/home/j/\.openclaw/workspace/[^"\x27\s|;)]+)', t):
        writes[m].add(os.path.basename(f))
conf = {k: v for k, v in writes.items() if len(v) > 1 and '.log' not in k and 'state/' not in k}
for k, v in list(conf.items())[:8]: issue('- 多脚本写同一文件：%s ← %s' % (k, ', '.join(sorted(v))))
if not conf: p('- 未发现冲突')
p('')
p('## 4) 安全红线扫描')
risky = []
for f in sh_files + py_files:
    try: t = open(f, errors='ignore').read()
    except Exception: continue
    b = os.path.basename(f)
    if b == 'audit-scripts.py': continue  # 自查器自身含规则字符串，跳过
    if re.search(r"rm\\s+-rf\\s+/(?!\s*\*\s*['\"])", t) and 'audit' not in b: risky.append(b + ' 含 rm -rf 绝对路径')
    if re.search(r'reset\s+--hard|push\s+--force', t): risky.append(b + ' 含 git 强制操作')
if risky: issue('- 需人工确认：' + ' | '.join(risky[:6]))
else: p('- 无 rm -rf / 强制 git')
p('')
p('## 5) 遗漏与优化')
scripts = set(os.path.basename(x) for x in sh_files + py_files)
refs = set()
for d in [W + '/tools', W + '/state', W + '/docs']:
    for f in glob.glob(d + '/*'):
        try: t = open(f, errors='ignore').read()
        except Exception: continue
        for s in scripts: 
            if s in t and os.path.basename(f) != s: refs.add(s)
orphan = sorted(s for s in scripts if s not in refs and not s.startswith(('_', 'test')) and not s.endswith(('.pyc',)))
p('- 未被任何脚本/台账提及（可能废弃，非故障）：%d 个' % len(orphan))
# 2026-10-26 A6 修：原用 '/tmp/' 子串判断，把 state/tmp/ 与 ~/.openclaw/tmp/ 也当成 /tmp（假报）。
#  改为「/tmp/ 前面不是字母数字/点」才算真正写内存盘。
_TMPRE = re.compile(r'(?<![\w.])/tmp/')
# tmp-watch.sh 只在提示语里提到 /tmp（它本身就是监控 /tmp 的），不算写入
_TMP_OK = {'tmp-watch.sh'}
# 2026-10-26 A6 二次修：区分「写」与「读」。原实现只要出现 /tmp/ 就算写，
#   把 ls/cat/grep/glob/读日志 这类只读用法也当违规（footer/openclaw-health/
#   pkgs-backup/agent-replies-since 实为只读，属假报）。只认真正的写入形态。
_TMP_WRITE = re.compile(r'(>>?[^>]|\btee\b|\bmktemp\b|\bcp\b|\bmv\b|\btouch\b|\binstall\b|--output\b|\bopen\([^)]*\x27w|\x22w|write_text|\.write\()')

def _tmp_writes(path):
    try:
        for ln in open(path, errors='ignore'):
            code = ln.split('#')[0]
            if _TMPRE.search(code) and _TMP_WRITE.search(code):
                return True
    except Exception:
        return False
    return False

tmpuse = [os.path.basename(f) for f in sh_files + py_files
          if os.path.basename(f) not in _TMP_OK and _tmp_writes(f)]
p('- 仍写 /tmp（内存盘）：' + (', '.join(tmpuse[:6]) or '无'))
p('- .bak 备份残留：%d 个' % len(glob.glob(W + '/tools/*.bak*')))
p('')
p('## 6) 定时任务')
try:
    # 2026-10-26 A5 修：改用 cron list --json 取精确名，避免表格列宽截断造成"同名"误报
    r = subprocess.run(['openclaw','cron','list','--json'], capture_output=True, text=True, timeout=120)
    _jobs = json.loads(r.stdout).get('jobs', [])
    lines = ['%s - %s - %s' % (j.get('id','')[:8], j.get('name',''), j.get('status',''))
             for j in _jobs if str(j.get('status','')).lower() in ('error','failed')]
    errs = [l for l in lines if re.search('error|failed', l, re.I)]
    names = collections.Counter(j.get('name','').strip() for j in _jobs if j.get('name','').strip())
    if errs:
        for l in errs:
            issue('- 定时任务异常：' + ' '.join(l.split())[:170])
    else: p('- 定时任务无 error/failed')
    dup = [n for n, c in names.items() if c > 1]
    if dup: issue('- 同名任务重复：' + ', '.join(dup[:5]))
except Exception as e:
    p('- 取不到定时任务列表：%s' % e)
p('')
p('## 结论')
p('- 发现问题：%d 项' % issues)
open(W + '/state/script-audit.md','w').write('\n'.join(out))
if issues:
    print('⚠️ 脚本自查发现问题 %d 项：' % issues)
    for l in out:
        if l.startswith('- ') and ('错' in l or '需人工' in l or '异常' in l or '重复' in l or '冲突' in l):
            print(l)
    print('报告：state/script-audit.md')
else:
    print('')