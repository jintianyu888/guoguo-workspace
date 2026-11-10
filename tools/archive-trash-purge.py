
#!/usr/bin/env python3
# archive-trash-purge.py v1.1 — 保留回收站(_trash)到期归档清理（2026-11-10 主公批准 #972）
# 规则：只删 <archives>/_trash/<批次>/*.tar.gz，且同时满足
#   1) mtime 距今 >= MIN_DAYS（默认 7 天）
#   2) 全部副本里，除自己外还有 >=2 份「同尺寸」副本
#   3) 兜底：同一尺寸至少留 1 份，绝不删到 0
# 默认 DRY（只打印），--apply 才真删；每次删除写台账 state/backup/archive-purge-ledger.jsonl
import os, sys, json, time, glob, datetime

BASES = ['/mnt/x/openclaw-backups', '/mnt/h/openclaw-backups',
         '/mnt/d/openclaw-backups', '/mnt/e/openclaw-backups']
LEDGER = '/home/j/.openclaw/workspace/state/backup/archive-purge-ledger.jsonl'
MIN_DAYS = 7
APPLY = '--apply' in sys.argv
# 2026-11-10 18:20 主公令：超过 7 天的存档正常没用了 —— 允许删掉「最后一份」
ALLOW_LAST = '--allow-last-copy' in sys.argv
for a in sys.argv[1:]:
    if a.startswith('--min-days='):
        MIN_DAYS = int(a.split('=', 1)[1])

def human(n):
    for u in ('B', 'K', 'M', 'G', 'T'):
        if abs(n) < 1024 or u == 'T':
            return ('%.0f%s' % (n, u)) if u in 'BK' else ('%.1f%s' % (n, u))
        n /= 1024.0

def in_trash(p):
    return '/_trash' in p

# 所有归档（含 _trash）按尺寸建索引
index = {}
for b in BASES:
    if not os.path.isdir(b):
        continue
    for f in os.listdir(b):
        if f.endswith('.tar.gz'):
            p = os.path.join(b, f)
            try:
                index.setdefault(os.path.getsize(p), []).append(p)
            except OSError:
                pass
    for f in glob.glob(os.path.join(b, '_trash', '*', '*.tar.gz')):
        try:
            index.setdefault(os.path.getsize(f), []).append(f)
        except OSError:
            pass

cut = time.time() - MIN_DAYS * 86400
cands, keep = [], []
for p, copylist in index.items():
    trash_rows = []
    for f in copylist:
        if not in_trash(f):
            continue
        try:
            st = os.stat(f)
        except OSError:
            continue
        age_d = (time.time() - st.st_mtime) / 86400.0
        trash_rows.append(dict(path=f, size=p, age_days=round(age_d, 1), copies=len(copylist) - 1,
                               copy_paths=[x for x in copylist if x != f][:4]))
    if not trash_rows:
        continue
    live = len(copylist) - len(trash_rows)          # _trash 之外的副本数
    trash_rows.sort(key=lambda r: os.path.getmtime(r['path']), reverse=True)   # 新的在前
    keep_n = 0 if (live >= 1 or ALLOW_LAST) else 1  # 默认 _trash 外无副本必留 1 份；--allow-last-copy 可删最后一份
    for r in trash_rows[:keep_n]:
        r['note'] = '最后一副本，保留'
        keep.append(r)
    for r in trash_rows[keep_n:]:
        if r['age_days'] >= MIN_DAYS and (r['copies'] >= 2 or ALLOW_LAST):
            cands.append(r)
        else:
            keep.append(r)

print('保留回收站到期清理 %s（MIN_DAYS=%d，%s）' % (datetime.date.today().isoformat(), MIN_DAYS,
                                                 'APPLY' if APPLY else 'DRY'))
print('  可删 %d 份 合计 %s' % (len(cands), human(sum(r['size'] for r in cands))))
for r in cands:
    print('    %-72s %8s 龄 %.1f天 副本 %d' % (r['path'], human(r['size']), r['age_days'], r['copies']))
print('  保留 %d 份 合计 %s' % (len(keep), human(sum(r['size'] for r in keep))))
for r in keep[:10]:
    why = r.get('note') or ('副本不足(%d)' % r['copies'] if r['copies'] < 2 else '未到期(%.1f天)' % r['age_days'])
    print('    %-72s %8s %s' % (r['path'], human(r['size']), why))

if not APPLY:
    print('  DRY：未删除任何文件（加 --apply 执行）')
    sys.exit(0)

os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
freed = 0
ts = datetime.datetime.now().isoformat(timespec='seconds')
for r in cands:
    try:
        os.remove(r['path'])
        freed += r['size']
        with open(LEDGER, 'a') as fh:
            fh.write(json.dumps(dict(ts=ts, action='purge-archive-trash', **r), ensure_ascii=False) + '\n')
    except OSError as e:
        print('  删除失败 %s: %s' % (r['path'], e))
for b in BASES:
    for d in glob.glob(os.path.join(b, '_trash', '*')):
        try:
            os.rmdir(d)
        except OSError:
            pass
print('  实删 %d 份，释放 %s' % (len(cands), human(freed)))
