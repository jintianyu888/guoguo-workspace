#!/usr/bin/env python3
"""project-monitor.py - 项目监控巡检：每项都有哨兵；只在有问题时说话（零 token）"""
import os, re, subprocess, datetime, glob, json
W = '/home/j/.openclaw/workspace'
issues = []
info = []
def ok(s): info.append(s)
def bad(s): issues.append(s)

# 1) 备份：最近全量归档是否 26h 内
bks = sorted(glob.glob('/mnt/d/openclaw-backups/*openclaw-backup.tar.gz'))
if bks:
    # 用文件名里的时间戳判定（mtime 会因复制而失真）
    def fname_ts(p):
        m = re.search(r'(\\d{4}-\\d{2}-\\d{2})T(\\d{2})-(\\d{2})-(\\d{2})', os.path.basename(p))
        if not m: return 0
        try: return datetime.datetime.strptime('%s %s:%s:%s' % m.groups(), '%Y-%m-%d %H:%M:%S').timestamp()
        except Exception: return 0
    bks.sort(key=fname_ts)
    newest = bks[-1]; age = (datetime.datetime.now() - datetime.datetime.fromtimestamp(fname_ts(newest) or os.path.getmtime(newest)))
    gb = os.path.getsize(newest) / 1073741824.0
    if age.total_seconds() > 30*3600: bad('备份：最近全量归档 %.1f 小时前（>30h）' % (age.total_seconds()/3600))
    else: ok('备份：%.1fG · %.1f 小时前' % (gb, age.total_seconds()/3600))
else: bad('备份：找不到全量归档')

# 2) 下载：卡住判定
dl = W + '/state/dl'
if os.path.isdir(dl):
    files = glob.glob(dl + '/*')
    if files:
        newest = max(files, key=os.path.getmtime)
        mins = (datetime.datetime.now().timestamp() - os.path.getmtime(newest)) / 60
        procs = subprocess.run(['pgrep','-cf','wget|multi-dl|curl|dl-fast'], capture_output=True, text=True).stdout.strip() or '0'
        whl = len(glob.glob(dl + '/*.whl'))
        if whl: ok('下载：已完成 %d 个 wheel' % whl)
        elif mins > 20 and procs == '0': bad('下载：卡住（%.0f 分钟无写入 · 无进程）' % mins)
        else: ok('下载：进行中（%.0f 分钟前有写入 · 进程 %s）' % (mins, procs))

# 3) 关键工具与模型是否在位
for p, name in [(W+'/tools/asr','ASR 启动器'), (W+'/tools/ocr-file','OCR 启动器'), (W+'/tools/batch-extract.sh','夜间归档'), (W+'/tools/dl-watchdog.sh','下载看门狗'), (W+'/tools/audit-scripts.py','脚本自查')]:
    if not os.path.exists(p): bad('工具缺失：%s' % name)
m = glob.glob(W + '/tools/models/faster-whisper-*')
if not m: bad('ASR 模型缺失')
else: ok('ASR 模型：%d 档在位' % len(m))

# 4) 定时任务异常
try:
    r = subprocess.run(['openclaw','automations','list','--all'], capture_output=True, text=True, timeout=120)
    errs = [l for l in r.stdout.splitlines() if re.search(r'error|failed', l, re.I)]
    if errs: bad('定时任务异常 %d 条（首条：%s）' % (len(errs), errs[0].strip()[:80]))
    else: ok('定时任务：无 error/failed')
except Exception as e:
    ok('定时任务：取不到（%s）' % e)

# 5) 磁盘 / 内存盘 / GPU / 网关
du = subprocess.run(['df','-h','/','/tmp'], capture_output=True, text=True).stdout.splitlines()
for line in du[1:]:
    parts = line.split()
    if len(parts) >= 6:
        pct = int(parts[4].rstrip('%'))
        if parts[5] == '/' and pct >= 85: bad('磁盘 /：%d%%' % pct)
        if parts[5] == '/tmp' and pct >= 80: bad('内存盘 /tmp：%d%%' % pct)
        if parts[5] in ('/', '/tmp'): ok('%s：%d%%' % (parts[5], pct))
g = subprocess.run(['/usr/lib/wsl/lib/nvidia-smi','--query-gpu=utilization.gpu,memory.used,memory.free','--format=csv,noheader'], capture_output=True, text=True)
if g.returncode == 0: ok('GPU：%s' % g.stdout.strip())
else: bad('GPU：nvidia-smi 不可用')
gw = subprocess.run(['pgrep','-f','openclaw.*gateway'], capture_output=True, text=True).stdout.split()
if gw: ok('网关：PID %s 在跑' % gw[0])
else: bad('网关：进程不在！')

# 6) 管家凭据
try:
    r = subprocess.run(['openclaw','models','auth','list'], capture_output=True, text=True, timeout=60)
    if re.search(r'deepseek|local', r.stdout, re.I): ok('模型凭据：至少一个 provider 在位')
    else: bad('模型凭据：看不到 deepseek')
except Exception: pass

rep = ['# 项目监控巡检  ' + datetime.datetime.now().strftime('%F %T'), '']
rep.append('## 正常项（%d）' % len(info))
for i in info: rep.append('- OK ' + i)
rep.append('')
rep.append('## 问题项（%d）' % len(issues))
for i in issues: rep.append('- PROBLEM ' + i)
open(W + '/state/project-monitor.md','w').write('\n'.join(rep))
if issues:
    print('⚠️ 项目监控发现问题 %d 项：' % len(issues))
    for i in issues: print('- ' + i)
    print('报告：state/project-monitor.md')
else:
    print('')