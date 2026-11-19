#!/usr/bin/env python3
# d-trash-clean.py —— D:\openclaw-backups\_trash 清理：三重校验(名+大小+抽样SHA256)后才删
# 2026-10-21 主公批准第1/2步
import hashlib, os, shutil, sys, time

D = "/mnt/d/openclaw-backups/_trash"
ROOTS = ["/mnt/e/openclaw-backups", "/mnt/h/openclaw-backups"]
LOG = "/home/j/.openclaw/workspace/state/work/d-cleanup-20261021.log"
SAMPLE = 256 * 1024 * 1024  # 头尾各 256MB

def log(m):
    line = time.strftime("[%H:%M:%S] ") + m
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def sample_hash(path):
    h = hashlib.sha256(); sz = os.path.getsize(path)
    with open(path, "rb") as f:
        h.update(f.read(SAMPLE))
    if sz > SAMPLE * 2:
        with open(path, "rb") as f:
            f.seek(-SAMPLE, os.SEEK_END); h.update(f.read(SAMPLE))
    return h.hexdigest()

def find_same(name, size, root):
    hits = []
    for dp, dn, fn in os.walk(root):
        if name in fn:
            p = os.path.join(dp, name)
            try:
                if os.path.getsize(p) == size: hits.append(p)
            except OSError: pass
    return hits

def main():
    dry = "--apply" not in sys.argv
    log("=== 开始 dry=%s ===" % dry)
    victims = []
    for dp, dn, fn in os.walk(D):
        for f in fn:
            p = os.path.join(dp, f)
            try: sz = os.path.getsize(p)
            except OSError: continue
            if sz > 1024**3: victims.append((p, f, sz))
    log("待处理大文件 %d 个" % len(victims))
    reclaimed = 0
    for p, name, sz in victims:
        log("检查 %s (%.1fG)" % (p, sz/1024**3))
        dh = sample_hash(p)
        ok = True
        for root in ROOTS:
            cands = find_same(name, sz, root)
            if not cands:
                log("  ✗ %s 无同名同大小副本" % root); ok = False; continue
            match = None
            for c in cands[:2]:
                if sample_hash(c) == dh: match = c; break
            if match: log("  ✓ %s 哈希一致 %s" % (root, match))
            else: log("  ✗ %s 哈希不一致 (%s)" % (root, cands[0])); ok = False
        if ok:
            log("  → 三重校验通过%s" % ("（dry）" if dry else "，删除"))
            if not dry:
                os.remove(p); reclaimed += sz
        else:
            log("  → 保留")
    # 空目录清理
    removed_dirs = 0
    for dp, dn, fn in os.walk(D, topdown=False):
        if dp == D: continue
        try:
            if not os.listdir(dp):
                log("删空目录 %s" % dp)
                if not dry: os.rmdir(dp); removed_dirs += 1
        except OSError: pass
    log("完成：回收 %.1fG，删空目录 %d" % (reclaimed/1024**3, removed_dirs))
    if not dry:
        os.system("df -h /mnt/d | tail -1")

main()
