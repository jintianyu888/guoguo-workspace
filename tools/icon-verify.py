# -*- coding: utf-8 -*-
"""icon-verify.py —— 校验飞书应用图标是否等于本地新版（mad<18 视为一致）"""
import json, sys, urllib.request
from PIL import Image, ImageChops
W = "/home/j/.openclaw/workspace"
PAIRS = {'jianji':'剪辑管家','print3d':'3D打印管家','info':'信息板管家','security':'安保管家','maint':'维护管家',
 'law':'法律管家','gege':'格格','health':'健康管家','health-doudou':'健康豆豆管家','health-wife':'健康媳妇管家',
 'health-mom':'健康妈妈管家','company1':'公司1管家','company2':'公司2管家','company3':'公司3管家','paike':'排课管家',
 'agant':'Agant老师','work':'干活管家','hermess':'Hermess'}
d = {r['name']: r for r in json.load(open(W + "/state/icons/current/index.json"))}
bad = []
for k, cn in PAIRS.items():
    r = d.get(cn)
    if not r: bad.append((cn, "missing")); continue
    b = urllib.request.urlopen(urllib.request.Request(r['src'], headers={'User-Agent': 'Mozilla/5.0'}), timeout=20).read()
    p = "/tmp/iv-%s.png" % k; open(p, 'wb').write(b)
    a = Image.open(p).convert('RGB').resize((64, 64))
    n = Image.open(W + "/state/icons/new/%s.png" % k).convert('RGB').resize((64, 64))
    mad = sum(sum(q) for q in ImageChops.difference(a, n).getdata()) / (64 * 64 * 3)
    print("%-12s mad=%5.2f %s" % (cn, mad, "OK" if mad < 18 else "MISMATCH"))
    if mad >= 18: bad.append((cn, round(mad, 1)))
print("RESULT", "GREEN" if not bad else "RED " + str(bad))
sys.exit(0 if not bad else 1)
