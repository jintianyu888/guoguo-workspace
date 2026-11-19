#!/usr/bin/env python3
"""把聚类结果与已建人脸库比对，挑出「库里没有的人」，产物给主公认人。
用法: facepy tools/face-unknown-groups.py [--min-sim 0.55] [--min-imgs 2]
读 state/faces/groups2.json + 每组成员图，用 db.npz 的质心比对；
相似度低于 min-sim 视为未知，按组输出到 state/faces/candidates/<日期>/。
"""
import os, sys, json, shutil, argparse, datetime
import numpy as np
import importlib.util, cv2

W = '/home/j/.openclaw/workspace'
spec = importlib.util.spec_from_file_location('fr', os.path.join(W, 'tools/face-recognize.py'))
fr = importlib.util.module_from_spec(spec); spec.loader.exec_module(fr)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--min-sim', type=float, default=0.55)
    ap.add_argument('--min-imgs', type=int, default=2)
    a = ap.parse_args()

    gp = os.path.join(W, 'state/faces/groups2.json')
    if not os.path.exists(gp): sys.exit('缺少 groups2.json，先跑 face-quality-index.py')
    groups = json.load(open(gp))
    labels, samples = fr.load_db()
    if not len(labels):
        print('库为空，全部视为未知'); cents = {}
    else:
        cents = {}
        for nm in set(labels):
            v = samples[[i for i, l in enumerate(labels) if l == nm]].mean(axis=0)
            cents[nm] = v / np.linalg.norm(v)

    day = datetime.date.today().isoformat()
    outdir = os.path.join(W, 'state/faces/candidates', day)
    os.makedirs(outdir, exist_ok=True)
    src = os.path.join(W, 'state/faces/collected')

    unknown, known = [], []
    for grp in groups:
        if grp['count'] < a.min_imgs: continue
        vs = []
        for f in grp['files']:
            p = os.path.join(src, f)
            if not os.path.exists(p): continue
            fs = fr.faces_of(p)
            if not fs: continue
            b = max(fs, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
            vs.append(fr.norm(b.embedding))
        if not vs: continue
        c = np.mean(vs, axis=0); c = c / np.linalg.norm(c)
        best = (None, 0.0)
        for nm, cc in cents.items():
            s = float(c @ cc)
            if s > best[1]: best = (nm, s)
        rec = {'group': grp['group'], 'count': grp['count'], 'best_name': best[0], 'sim': round(best[1], 3)}
        (unknown if best[1] < a.min_sim else known).append(rec)

    unknown.sort(key=lambda r: -r['count'])
    for rec in unknown:
        sh = os.path.join(W, 'state/faces/sheets2', 'group_%d.jpg' % rec['group'])
        if os.path.exists(sh):
            shutil.copy2(sh, os.path.join(outdir, 'group_%d.jpg' % rec['group']))
    json.dump({'date': day, 'unknown': unknown, 'known': known},
              open(os.path.join(outdir, 'report.json'), 'w'), ensure_ascii=False, indent=1)
    print('未知组 %d 个，已匹配到库的组 %d 个' % (len(unknown), len(known)))
    for r in unknown:
        print('  组%d (%d张) 最像 %s %.3f' % (r['group'], r['count'], r['best_name'], r['sim']))
    if unknown:
        print('候选图目录: %s' % outdir)

if __name__ == '__main__':
    main()
