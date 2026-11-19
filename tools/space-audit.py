
import os, json, subprocess, time, datetime, glob

W = '/home/j/.openclaw/workspace'
OUT = os.path.join(W, 'state/disk')
os.makedirs(OUT, exist_ok=True)
TODAY = datetime.date.today().isoformat()

def sh(cmd, t=60):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t)
        return p.stdout.strip()
    except Exception:
        return ''

def du_bytes(path, t=90):
    o = sh("du -s --block-size=1 %s 2>/dev/null | awk '{print $1}'" % json.dumps(path), t)
    try: return int(o.split()[0]) if o else 0
    except: return 0

def human(n):
    for u in ('B','K','M','G','T'):
        if abs(n) < 1024 or u=='T': return ('%.0f%s' % (n,u)) if u in 'BK' else ('%.1f%s' % (n,u))
        n /= 1024.0

# 1) 磁盘水位（逻辑盘）
mounts = [('/', 'WSL根'), ('/mnt/d','D'), ('/mnt/e','E'), ('/mnt/h','H'), ('/mnt/x','X'), ('/mnt/nas','NAS')]
disks = []
for m, label in mounts:
    if not os.path.exists(m): continue
    o = sh("df -B1 %s 2>/dev/null | awk 'NR==2{print $2,$3,$4,$5}'" % m, 30)
    parts = o.split()
    if len(parts) < 3: continue
    try:
        total, used, avail = int(parts[0]), int(parts[1]), int(parts[2])
    except: continue
    disks.append(dict(mount=m, label=label, total=total, used=used, avail=avail,
                      pct=round(used*100.0/total, 1) if total else 0))

# 2) WSL 镜像膨胀
vhdx = '/mnt/x/WSL/Ubuntu/ext4.vhdx'
vh = {}
if os.path.exists(vhdx):
    logical = os.stat(vhdx).st_size
    alloc = du_bytes(vhdx, 120)
    root_used = next((d['used'] for d in disks if d['mount'] == '/'), 0)
    vh = dict(logical=logical, alloc=alloc, guest_used=root_used,
              inflation=round(alloc*100.0/root_used, 1) if root_used else 0,
              reclaimable=max(alloc - root_used, 0))

# 3) 保留回收站（_trash / openclaw-trash）—— 按盘汇总 + 最老批次
trash_roots = []
for base in ('/mnt/x/openclaw-backups', '/mnt/h/openclaw-backups', '/mnt/d/openclaw-backups',
             '/mnt/e/openclaw-backups', '/home/j/.openclaw/state', '/home/j/.openclaw/workspace/state'):
    for name in ('_trash', '_trash-20261107'):
        p = os.path.join(base, name)
        if os.path.isdir(p):
            kids = sorted(glob.glob(os.path.join(p, '*')))
            size = du_bytes(p, 120)
            oldest = None
            if kids:
                try: oldest = datetime.date.fromtimestamp(min(os.path.getmtime(k) for k in kids)).isoformat()
                except: pass
            trash_roots.append(dict(path=p, size=size, batches=len(kids), oldest=oldest))

# 4) 残包/垃圾文件（.part / .bad / .crdownload / .tmp）>24h
residue = []
cutoff = time.time() - 86400
for base in ('/mnt/x/openclaw-backups', '/mnt/h/openclaw-backups', '/mnt/d/openclaw-backups',
             '/mnt/e/openclaw-backups', '/mnt/x/wsl-backup'):
    if not os.path.isdir(base): continue
    for root, dirs, files in os.walk(base):
        if root.count(os.sep) - base.count(os.sep) > 2:
            dirs[:] = []
            continue
        for f in files:
            if any(f.endswith(s) for s in ('.part', '.crdownload', '.tmp')) or '.bad' in f:
                fp = os.path.join(root, f)
                try:
                    st = os.stat(fp)
                    bad = '.bad' in f
                    if bad or st.st_mtime < cutoff:
                        residue.append(dict(path=fp, size=st.st_size,
                                            age_h=int((time.time()-st.st_mtime)/3600)))
                except: pass

# 5) 归档数量 vs 保留策略
KEEP = {'/mnt/x/openclaw-backups': 2, '/mnt/e/openclaw-backups': 7, '/mnt/h/openclaw-backups': 7,
        '/mnt/d/openclaw-backups': 1, '/mnt/nas/archive/jinyu/openclaw-archives': 0}
archives = []
for d, keep in KEEP.items():
    if not os.path.isdir(d): continue
    files = [f for f in os.listdir(d) if f.endswith('.tar.gz') and 'openclaw-backup' in f]
    files.sort(reverse=True)
    archives.append(dict(dir=d, count=len(files), keep=keep,
                         excess=max(len(files)-keep, 0) if keep else 0,
                         newest=files[0] if files else None))

# 6) 大文件 Top（>15G）
big = []
for base in ('/mnt/x/openclaw-backups', '/mnt/x/wsl-backup', '/mnt/h/openclaw-backups',
             '/mnt/d/openclaw-backups', '/mnt/e/openclaw-backups'):
    if not os.path.isdir(base): continue
    o = sh("find %s -maxdepth 2 -type f -size +15G -printf '%%s\t%%p\n' 2>/dev/null" % json.dumps(base), 90)
    for line in o.splitlines():
        try:
            s, p = line.split('\t', 1)
            big.append(dict(path=p, size=int(s)))
        except: pass
big.sort(key=lambda x: -x['size'])
big = big[:10]

# 7) 趋势
hist_path = os.path.join(OUT, 'history.jsonl')
snap = dict(ts=int(time.time()), date=TODAY,
            used={d['mount']: d['used'] for d in disks},
            vhdx=vh.get('alloc'), trash=sum(t['size'] for t in trash_roots),
            residue=sum(r['size'] for r in residue))
prev = None
if os.path.exists(hist_path):
    try:
        lines = [l for l in open(hist_path).read().splitlines() if l.strip()]
        if lines: prev = json.loads(lines[-1])
    except: prev = None
with open(hist_path, 'a') as f:
    f.write(json.dumps(snap, ensure_ascii=False) + '\n')

# 8) 判定
flags = []
for d in disks:
    if d['label'] == 'NAS': continue
    if d['pct'] >= 90: flags.append(('P0', '%s 水位 %.1f%%（可用 %s）' % (d['label'], d['pct'], human(d['avail']))))
    elif d['pct'] >= 85: flags.append(('P1', '%s 水位 %.1f%%（可用 %s）' % (d['label'], d['pct'], human(d['avail']))))
if vh:
    if vh['inflation'] >= 125: flags.append(('P1', 'WSL 镜像膨胀 %.0f%%（占盘 %s / 实占 %s，可压 %s）' % (vh['inflation'], human(vh['alloc']), human(vh['guest_used']), human(vh['reclaimable']))) )
    elif vh['inflation'] >= 118: flags.append(('P2', 'WSL 镜像膨胀 %.0f%%（可压 %s）' % (vh['inflation'], human(vh['reclaimable']))) )
tsz = sum(t['size'] for t in trash_roots)
if tsz >= 100*1024**3: flags.append(('P1', '保留回收站合计 %s（清理不覆盖，需人工/策略处理）' % human(tsz)))
elif tsz >= 30*1024**3: flags.append(('P2', '保留回收站 %s' % human(tsz)))
rsz = sum(r['size'] for r in residue)
if rsz >= 10*1024**3: flags.append(('P1', '残包 %s（%d 个 >24h）' % (human(rsz), len(residue))))
elif rsz >= 2*1024**3: flags.append(('P2', '残包 %s' % human(rsz)))
for a in archives:
    if a['excess'] > 0 and a['keep']:
        flags.append(('P2', '%s 归档 %d 份 > 保留 %d 份' % (a['dir'], a['count'], a['keep'])))

result = dict(date=TODAY, ts=snap['ts'], disks=disks, vhdx=vh, trash=trash_roots,
              residue=residue, archives=archives, big=big, flags=flags,
              totals=dict(trash=tsz, residue=rsz))

with open(os.path.join(OUT, 'latest.json'), 'w') as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

# 9) 输出（brief 模式只给结论行）
lines = []
lines.append('体积体检 %s' % TODAY)
for d in disks:
    lines.append('  %-6s %5.1f%% 已用 %s / %s 可用 %s' % (d['label'], d['pct'], human(d['used']), human(d['total']), human(d['avail'])))
if vh:
    lines.append('  镜像   逻辑 %s 占盘 %s 实占 %s 膨胀 %.0f%% 可压 %s' % (
        human(vh['logical']), human(vh['alloc']), human(vh['guest_used']), vh['inflation'], human(vh['reclaimable'])))
if trash_roots:
    for t in sorted(trash_roots, key=lambda x: -x['size'])[:6]:
        if t['size'] > 0:
            lines.append('  回收站 %-42s %s  %d 批 最老 %s' % (t['path'].replace('/mnt',''), human(t['size']), t['batches'], t['oldest']))
if residue:
    lines.append('  残包   %d 个 合计 %s' % (len(residue), human(rsz)))
for a in archives:
    lines.append('  归档   %-38s %d 份 (保留 %s)' % (a['dir'].replace('/mnt',''), a['count'], a['keep'] or '-'))
if big:
    b = big[0]
    lines.append('  最大文件 %s  %s' % (human(b['size']), b['path'].replace('/mnt','')))
if prev and prev.get('used'):
    deltas = []
    for d in disks:
        pu = prev['used'].get(d['mount'])
        if pu: deltas.append('%s %+.1fG' % (d['label'], (d['used']-pu)/1024**3))
    if deltas: lines.append('  较上次  ' + '  '.join(deltas))
if flags:
    lines.append('  判定：')
    for lvl, msg in flags: lines.append('    %s %s' % (lvl, msg))
else:
    lines.append('  判定：OK（无越线项）')
if '--line' in os.sys.argv:
    # 精简一行式（给简报用）
    compact = []
    for d in disks:
        if d['pct'] >= 70: compact.append('%s %.0f%%(剩%s)' % (d['label'], d['pct'], human(d['avail'])))
    if vh and vh['inflation'] >= 110:
        compact.append('镜像膨胀 %.0f%%(可压%s)' % (vh['inflation'], human(vh['reclaimable'])))
    if tsz >= 10*1024**3: compact.append('保留回收站 %s' % human(tsz))
    if rsz >= 1024**3: compact.append('残包 %s' % human(rsz))
    p1 = [m for lv, m in flags if lv in ('P0','P1')]
    if p1: compact.append('越线 %d 项' % len(p1))
    print(' ｜ '.join(compact) if compact else '各盘水位正常')
    raise SystemExit(0)

print('\n'.join(lines))
