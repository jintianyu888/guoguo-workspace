#!/usr/bin/env python3
"""人脸库批量录入 + 盲测
目录约定：<root>/<姓名>/*.jpg|png —— 每人一个目录。
默认每人留 2 张做盲测（不注册），其余注册进 db.npz；随后用留出的图做盲测，输出命中率。
用法：
  source tools/face-env.sh
  facepy tools/face-enroll-dir.py --root /mnt/e/face-enroll            # 入库+盲测
  facepy tools/face-enroll-dir.py --root X --dry-run                   # 只看会怎么做
  facepy tools/face-enroll-dir.py --root X --threshold 0.38 --holdout 2
只读原图；db 写入走 face-recognize 的同一格式（labels + samples 512 维）。
"""
import argparse, glob, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2
import importlib.util

spec = importlib.util.spec_from_file_location("fr", os.path.join(os.path.dirname(os.path.abspath(__file__)), "face-recognize.py"))
fr = importlib.util.module_from_spec(spec); spec.loader.exec_module(fr)

EXTS = ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG")

def imgs(d):
    out = []
    for e in EXTS: out += glob.glob(os.path.join(d, e))
    return sorted(set(out))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--holdout", type=int, default=2)
    ap.add_argument("--threshold", type=float, default=0.38)
    ap.add_argument("--cap", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reset-db", action="store_true", help="重建库（原库另存 .bak）")
    a = ap.parse_args()

    people = [d for d in sorted(os.listdir(a.root)) if os.path.isdir(os.path.join(a.root, d))]
    if not people: sys.exit("目录下没有子目录（应为 <root>/<姓名>/）")

    labels, samples = fr.load_db()
    if a.reset_db and len(labels):
        import shutil, time
        bak = fr.DBP + ".bak-%s" % time.strftime("%Y%m%d-%H%M%S")
        shutil.move(fr.DBP, bak); print("原库另存:", bak)
        labels, samples = [], np.zeros((0, 512), dtype=np.float32)

    plan = {}
    for p in people:
        fs = imgs(os.path.join(a.root, p))
        if not fs: print("  ! 跳过空目录", p); continue
        hold = fs[:a.holdout] if len(fs) > a.holdout else []
        use = fs[a.holdout:] if hold else fs
        plan[p] = (use, hold)
        print("%s: 共 %d 张 → 注册 %d / 盲测留出 %d" % (p, len(fs), len(use), len(hold)))

    if a.dry_run: return

    n_ok, n_fail = 0, []
    for name, (use, _) in plan.items():
        for f in use:
            fs = fr.faces_of(f)
            if not fs:
                print("  ! 没人脸:", f); continue
            b = max(fs, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
            labels, samples = fr.add_sample(labels, samples, name, fr.norm(b.embedding), a.cap)
            n_ok += 1
    fr.save_db(labels, samples)
    try: os.chmod(fr.DBP, 0o600)
    except OSError: pass
    print("入库完成：%d 张 -> %s（库内 %d 条样本）" % (n_ok, fr.DBP, len(labels)))

    print("\n盲测（阈值 %.2f，距离越小越像）：" % a.threshold)
    tot = hit = 0
    for name, (_, hold) in plan.items():
        for f in hold:
            fs = fr.faces_of(f)
            if not fs:
                print("  - %s：无脸，跳过 %s" % (name, os.path.basename(f))); continue
            b = max(fs, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
            who, sc = fr.best(fr.load_db()[0], fr.load_db()[1], fr.norm(b.embedding), a.threshold)
            tot += 1; ok = (who == name); hit += ok
            print("  %s %s -> %s (%.3f)" % ("✓" if ok else "✗", name, who, sc))
    if tot: print("盲测命中率 %d/%d" % (hit, tot))
    else: print("没有留出样本可测")

if __name__ == "__main__":
    main()
