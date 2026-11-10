#!/usr/bin/env python3
"""备份保留策略：最近 N 份 + 每日 1 份 + 每周 1 份 + 每月 1 份（默认演练，--apply 才真删）"""
import os, re, sys, glob, time, hashlib
def parse(path):
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})T(\d{2})-(\d{2})-(\d{2})', os.path.basename(path))
    if not m: return None
    return time.mktime(tuple(int(x) for x in m.groups()) + (0,0,-1))
# --- SAFE_DELETE_V1 (2026-10-17 双模型复核加固) ---
ALLOWED_ROOTS = ("/mnt/d/openclaw-backups", "/mnt/e/openclaw-backups", "/mnt/h/openclaw-backups")
def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
def _safe_target(path):
    rp = os.path.realpath(path)
    if rp in ("/", "/mnt", "/mnt/d", "/mnt/e", "/mnt/h"):
        return None
    if not any(rp.startswith(r + os.sep) for r in ALLOWED_ROOTS):
        return None
    return rp
def _has_copy_elsewhere(path):
    rp = os.path.realpath(path)
    name = os.path.basename(rp)
    try:
        want = _sha256(rp)
    except Exception:
        return False, "无法计算哈希"
    for root in ALLOWED_ROOTS:
        cand = os.path.join(root, name)
        if os.path.realpath(cand) == rp:
            continue
        if not os.path.exists(cand):
            continue
        try:
            # 三重校验：文件名(同名) + 大小 + SHA256，缺一不删
            if os.path.getsize(cand) != os.path.getsize(rp):
                continue
            if _sha256(cand) == want:
                return True, cand
        except Exception:
            continue
    return False, "别处无同哈希副本"

def plan(paths, keep_n):
    items = sorted(((parse(p), p) for p in paths if parse(p)), key=lambda x: -x[0])
    keep = set()
    for _, p in items[:keep_n]: keep.add(p)              # 最近 N 份
    seen = {'day': set(), 'week': set(), 'month': set()}
    for ts, p in items:                                   # 每日/每周/每月 各留 1 份
        lt = time.localtime(ts)
        for k, key in (('day', time.strftime('%Y-%m-%d', lt)),
                       ('week', time.strftime('%Y-W%W', lt)),
                       ('month', time.strftime('%Y-%m', lt))):
            if key not in seen[k]:
                seen[k].add(key); keep.add(p)
    return [p for _, p in items if p in keep], [p for _, p in items if p not in keep], items
def main():
    apply_ = '--apply' in sys.argv
    root = sys.argv[sys.argv.index('--root')+1] if '--root' in sys.argv else '/home/j/Backups'
    keep_n = int(sys.argv[sys.argv.index('--keep')+1]) if '--keep' in sys.argv else 14
    paths = sorted(glob.glob(os.path.join(root, '*.tar.gz')))
    if not paths: print(f'(无归档: {root})'); return
    keep, dele, items = plan(paths, keep_n)
    print(f'📦 {root} · 共 {len(items)} 份 · 保留 {len(keep)} 份 · 可清理 {len(dele)} 份' + ('  [演练]' if not apply_ else '  [执行]'))
    max_del = int(sys.argv[sys.argv.index('--max-delete')+1]) if '--max-delete' in sys.argv else 50
    force = '--force' in sys.argv
    if dele and len(dele) > len(items) * 0.30 and not force:
        print('   \u26d4 \u7194\u65ad\uff1a\u5f85\u5220 %d \u4efd / \u5171 %d \u4efd\uff08\u8d85 30%%\uff09\uff0c\u9700 --force \u786e\u8ba4' % (len(dele), len(items)))
        return
    todo = dele[:max_del]
    if len(dele) > max_del:
        print('   \u2757 \u672c\u6b21\u6700\u591a\u5220 %d \u4efd\uff0c\u5269\u4f59 %d \u4efd\u7559\u5f85\u4e0b\u6b21' % (max_del, len(dele)-max_del))
    shown = done = refused = failed = 0
    for p in todo:
        if shown < 10:
            print('   - \u5220', os.path.basename(p)); shown += 1
        if apply_:
            tgt = _safe_target(p)
            if not tgt:
                print('     \u26d4 \u8df3\u8fc7\uff08\u8def\u5f84\u4e0d\u5728\u5141\u8bb8\u7684\u5907\u4efd\u6839\u76ee\u5f55\u5185\uff09'); refused += 1; continue
            ok, info = _has_copy_elsewhere(tgt)
            if not ok:
                print('     \u26d4 \u62d2\u7edd\u5220\u9664\uff08%s\uff09' % info); refused += 1; continue
            try:
                os.remove(tgt); done += 1
            except OSError as e:
                print('     \u26d4 \u5220\u9664\u5931\u8d25\uff08%s\uff09' % e); failed += 1
    if dele:
        print('   [汇总] 共 %d 份待删：处理 %d，已删 %d，拒绝 %d，失败 %d' % (len(dele), len(todo), done, refused, failed))
    if not dele: print('   ✅ 无需清理')
if __name__ == '__main__': main()
