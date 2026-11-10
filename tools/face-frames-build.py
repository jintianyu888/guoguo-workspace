#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""face-frames-build.py —— 从监控原尺寸帧建人脸库（2026-11-07 主公令：不再等手机照）

流程：检测人脸 → 质量闸(检测分/像素/正面度) → 裁图 → 特征 → 聚类 → 拼图供认人
用法（venv）：
  source tools/face-env.sh
  FACE_GPU=1 FACE_DET_SIZE=640 python3 tools/face-frames-build.py --root state/faces/nvrframes --out state/faces/from-frames
产出：crops/*.jpg、emb.npz、groups.json、sheet-*.jpg（每组一张，带编号）、report.md
"""
import os, sys, glob, json, argparse, datetime
import numpy as np, cv2

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WS, 'tools'))
import importlib.util
spec = importlib.util.spec_from_file_location('fr', os.path.join(WS, 'tools', 'face-recognize.py'))
fr = importlib.util.module_from_spec(spec); spec.loader.exec_module(fr)


def frontal(f):
    """用 5 点关键点估正面度：返回 (yaw_ratio, pitch_ratio)"""
    try:
        k = f.kps; x0, y0, x1, y1 = f.bbox
        w = max(1.0, x1 - x0); h = max(1.0, y1 - y0)
        le, re = k[0], k[1]; nose = k[2]
        eye_mid_x = (le[0] + re[0]) / 2.0
        yaw = abs(nose[0] - eye_mid_x) / w
        eye_mid_y = (le[1] + re[1]) / 2.0
        pitch = abs(nose[1] - eye_mid_y) / h
        return yaw, pitch
    except Exception:
        return 9.0, 9.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=WS + '/state/faces/nvrframes')
    ap.add_argument('--out', default=WS + '/state/faces/from-frames')
    ap.add_argument('--min-det', type=float, default=0.55)
    ap.add_argument('--min-size', type=int, default=64)
    ap.add_argument('--max-yaw', type=float, default=0.18)
    ap.add_argument('--max-pitch', type=float, default=0.20)
    ap.add_argument('--thr', type=float, default=0.45, help='聚类相似度阈值(余弦)')
    ap.add_argument('--max-frames', type=int, default=0)
    a = ap.parse_args()
    for d in ('crops',):
        os.makedirs(os.path.join(a.out, d), exist_ok=True)

    files = []
    for e in ('*.jpg', '*.jpeg', '*.png'):
        files += glob.glob(os.path.join(a.root, '**', e), recursive=True)
    files = sorted(set(files))
    if a.max_frames:
        files = files[:a.max_frames]
    if not files:
        print('没有帧可处理：%s' % a.root); return 2

    model = fr.app()
    kept, stats = [], {'frames': len(files), 'faces': 0, 'pass': 0, 'nofaces': 0}
    for p in files:
        im = cv2.imread(p)
        if im is None:
            continue
        faces = model.get(im)
        if not faces:
            stats['nofaces'] += 1
            continue
        for i, f in enumerate(faces):
            stats['faces'] += 1
            x0, y0, x1, y1 = f.bbox
            side = min(x1 - x0, y1 - y0)
            yaw, pitch = frontal(f)
            det = float(getattr(f, 'det_score', 0.0))
            if det < a.min_det or side < a.min_size or yaw > a.max_yaw or pitch > a.max_pitch:
                continue
            m = 0.2 * side
            X0 = max(0, int(x0 - m)); Y0 = max(0, int(y0 - m))
            X1 = min(im.shape[1], int(x1 + m)); Y1 = min(im.shape[0], int(y1 + m))
            crop = im[Y0:Y1, X0:X1]
            if crop.size == 0:
                continue
            name = '%s_%02d.jpg' % (os.path.basename(p).rsplit('.', 1)[0], i)
            cp = os.path.join(a.out, 'crops', name)
            cv2.imwrite(cp, crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
            kept.append({'file': cp, 'src': p, 'det': round(det, 3), 'side': int(side),
                         'yaw': round(yaw, 3), 'pitch': round(pitch, 3), 'emb': f.normed_embedding})
            stats['pass'] += 1

    if not kept:
        print(json.dumps(stats, ensure_ascii=False)); print('无合格人脸'); return 3

    E = np.stack([k['emb'] for k in kept])
    # 贪心聚类：相似度 >= thr 归入已有组，否则新组
    groups = []
    for i, k in enumerate(kept):
        best, bi = -1, -1
        for gi, g in enumerate(groups):
            sim = float(np.dot(E[i], g['centroid']))
            if sim > best:
                best, bi = sim, gi
        if best >= a.thr:
            g = groups[bi]
            g['idx'].append(i)
            g['centroid'] = (g['centroid'] * len(g['idx']) + E[i]) / (len(g['idx']) + 1)
        else:
            groups.append({'idx': [i], 'centroid': E[i].copy()})
    groups.sort(key=lambda g: -len(g['idx']))

    # 每组选代表（检测分×尺寸最大）
    sheet_rows = []
    gjson = []
    for gi, g in enumerate(groups, 1):
        members = g['idx']
        best = max(members, key=lambda i: kept[i]['det'] * kept[i]['side'])
        gjson.append({'no': gi, 'count': len(members), 'best': kept[best]['file'],
                      'samples': [kept[i]['file'] for i in members[:6]],
                      'det': kept[best]['det'], 'side': kept[best]['side']})
        img = cv2.imread(kept[best]['file'])
        cell = 220
        canvas = np.zeros((cell, cell, 3), np.uint8)
        h, w = img.shape[:2]
        s = min(cell / max(1, w), cell / max(1, h))
        rs = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))))
        y = (cell - rs.shape[0]) // 2; x = (cell - rs.shape[1]) // 2
        canvas[y:y + rs.shape[0], x:x + rs.shape[1]] = rs
        cv2.putText(canvas, str(gi), (6, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        sheet_rows.append(canvas)

    cols = min(6, len(sheet_rows))
    rows = (len(sheet_rows) + cols - 1) // cols
    sheet = np.zeros((rows * 220, cols * 220, 3), np.uint8)
    for i, im in enumerate(sheet_rows):
        r, c = divmod(i, cols)
        sheet[r * 220:(r + 1) * 220, c * 220:(c + 1) * 220] = im
    sp = os.path.join(a.out, 'sheet-all.jpg')
    cv2.imwrite(sp, sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])

    np.savez(os.path.join(a.out, 'emb.npz'), files=np.array([k['file'] for k in kept]), emb=E)
    json.dump({'stats': stats, 'groups': gjson}, open(os.path.join(a.out, 'groups.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    lines = ['# 监控抽帧建库报告 %s' % datetime.datetime.now().strftime('%F %T'), '',
             '- 处理帧 %d｜检出人脸 %d｜过质量闸 %d｜无人脸帧 %d' % (stats['frames'], stats['faces'], stats['pass'], stats['nofaces']),
             '- 聚成 %d 组（阈值 %.2f）' % (len(groups), a.thr), '', '## 各组']
    for g in gjson[:40]:
        lines.append('- %d 号：%d 张，代表 %s（det %.2f, %dpx）' % (g['no'], g['count'], os.path.basename(g['best']), g['det'], g['side']))
    lines.append('')
    lines.append('拼图：%s' % sp)
    rep = '\n'.join(lines)
    open(os.path.join(a.out, 'report.md'), 'w', encoding='utf-8').write(rep + '\n')
    print(rep)
    return 0


if __name__ == '__main__':
    sys.exit(main())
