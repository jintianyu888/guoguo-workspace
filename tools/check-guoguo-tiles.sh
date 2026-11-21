#!/usr/bin/env bash
# 果果助手实况窗（30 格）规格校验 —— 2026-11-21 规格定稿 docs/实况窗规格-20261121.md（干活管家增量请求）
# 验三件事：
#   ① .pc>.m>.top>.lbl / .val / .val>small 三处生效 font-size 必须都是 15px
#   ② #hudcanvas 生效 z-index 必须 < 2（雨在内容层 .wrap z-index:2 之下）
#   ③ .pc>.m>.sub 必须保持 display:none（不许被重新显示）
# 用法：bash tools/check-guoguo-tiles.sh [文件]    rc=0 合规格；rc=1 规格被破坏
set -u
F="${1:-/home/j/openclaw-workspaces/work/果果助手/public/index.html}"
[ -f "$F" ] || { echo "MISSING $F"; exit 1; }
python3 - "$F" <<'PY'
import re,sys
f=sys.argv[1]
src=open(f,encoding='utf-8').read()
# 去掉 CSS 注释，避免注释里的字样误判
css=re.sub(r'/\*.*?\*/','',src,flags=re.S)
lines=css.split('\n')
rc=0
def last_match(pred):
    out=None
    for i,l in enumerate(lines):
        if pred(l): out=(i+1,l.strip())
    return out
print('== ① 格内三处字号 ==')
for name,pred in [
  ('标签 .lbl', lambda l: '.pc>.m>.top>.lbl' in l and 'font-size:' in l),
  ('数值 .val', lambda l: '.pc>.m>.top>.val' in l and 'font-size:' in l),
  ('单位 small', lambda l: '.pc>.m>.top>.val>small' in l and 'font-size:' in l),
]:
    hit=last_match(pred)
    if not hit:
        print('FAIL %s 没有找到 font-size 声明（规格要求 15px）' % name); rc=1; continue
    ln,text=hit
    vals=re.findall(r'font-size:\s*([0-9.]+px)',text)
    v=vals[-1] if vals else '?'
    ok = v=='15px'
    print('%s %s 行%d font-size=%s' % ('OK  ' if ok else 'FAIL', name, ln, v))
    if not ok: rc=1
print('== ② 字符雨层级 ==')
hit=last_match(lambda l: '#hudcanvas' in l and 'z-index:' in l)
if not hit:
    print('FAIL 没找到 #hudcanvas 的 z-index 声明'); rc=1
else:
    ln,text=hit
    z=re.findall(r'z-index:\s*(-?[0-9]+)',text)
    zi=int(z[-1]) if z else 999
    ok = zi < 2
    print('%s #hudcanvas 行%d z-index=%d（必须 <2）' % ('OK  ' if ok else 'FAIL', ln, zi))
    if not ok: rc=1
print('== ③ .sub 必须隐藏 ==')
hit=last_match(lambda l: '.pc>.m>.sub' in l and 'display:' in l)
if not hit:
    print('FAIL 没找到 .pc>.m>.sub 的 display 声明（规格要求 display:none）'); rc=1
else:
    ln,text=hit
    d=re.findall(r'display:\s*([a-z-]+)',text)
    dv=d[-1] if d else '?'
    ok = dv=='none'
    print('%s .sub 行%d display=%s' % ('OK  ' if ok else 'FAIL', ln, dv))
    if not ok: rc=1
print('== 结论 ==')
print('PASS 实况窗规格未被破坏' if rc==0 else 'FAIL 实况窗规格被改动，按 docs/实况窗规格-20261121.md 恢复后重跑')
sys.exit(rc)
PY

