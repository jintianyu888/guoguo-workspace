# -*- coding: utf-8 -*-
"""icon-forge.py v2 —— 统一视觉规范的应用图标生成器（240 逻辑 / 480 渲染）"""
import os

OUT = "/home/j/.openclaw/workspace/state/icons/new"
os.makedirs(OUT, exist_ok=True)
W, D, A, A2 = "#FFFFFF", "#E6EDF9", "#FFD9A8", "#FF9A2E"

def svg(uid, c1, c2, body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="480" height="480" viewBox="0 0 240 240">'
            f'<defs><linearGradient id="bg{uid}" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>'
            f'<filter id="sh{uid}" x="-30%" y="-30%" width="170%" height="170%">'
            '<feDropShadow dx="0" dy="3" stdDeviation="3.2" flood-color="#0b1c33" flood-opacity="0.22"/>'
            f'</filter></defs><rect width="240" height="240" fill="url(#bg{uid})"/>'
            f'<g filter="url(#sh{uid})">{body}</g></svg>')

def gear(cx, cy, r, fill, hole, teeth=9, tw=14, th=16):
    s = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>']
    for i in range(teeth):
        a = 360 / teeth * i
        s.append(f'<rect x="{cx-tw/2}" y="{cy-r-th+4}" width="{tw}" height="{th}" rx="4" fill="{fill}" transform="rotate({a} {cx} {cy})"/>')
    if hole:
        s.append(f'<circle cx="{cx}" cy="{cy}" r="{r*0.42}" fill="{hole}"/>')
    return "".join(s)

def heart(cx, cy, s=1.0, fill=W):
    return (f'<path transform="translate({cx} {cy}) scale({s}) translate(-60 -55)" fill="{fill}" '
            'd="M60 96 C30 72 8 54 8 33 C8 15 21 4 36 4 C47 4 56 10 60 19 C64 10 73 4 84 4 C99 4 112 15 112 33 C112 54 90 72 60 96 Z"/>')

ICONS = []

ICONS.append(("jianji", "#FF8A5B", "#D8342A", f'''
<g transform="translate(58 48)">
  <rect x="0" y="0" width="124" height="150" rx="16" fill="{W}"/>
  <g fill="#D8342A">
    <rect x="10" y="12" width="18" height="18" rx="4"/><rect x="10" y="42" width="18" height="18" rx="4"/>
    <rect x="10" y="72" width="18" height="18" rx="4"/><rect x="10" y="102" width="18" height="18" rx="4"/>
    <rect x="96" y="12" width="18" height="18" rx="4"/><rect x="96" y="42" width="18" height="18" rx="4"/>
    <rect x="96" y="72" width="18" height="18" rx="4"/><rect x="96" y="102" width="18" height="18" rx="4"/>
  </g>
  <path d="M44 50 L88 75 L44 100 Z" fill="#D8342A"/>
</g>
<circle cx="192" cy="56" r="12" fill="{A}"/>'''))

ICONS.append(("print3d", "#5B9BFF", "#2450C8", f'''
<g transform="translate(44 44)">
  <rect x="0" y="0" width="152" height="14" rx="7" fill="{W}"/>
  <rect x="0" y="0" width="14" height="112" rx="7" fill="{W}"/>
  <rect x="138" y="0" width="14" height="112" rx="7" fill="{W}"/>
  <rect x="52" y="14" width="48" height="28" rx="8" fill="{W}"/>
  <rect x="64" y="42" width="24" height="14" rx="4" fill="{D}"/>
  <path d="M70 56 h12 l-6 12 Z" fill="{A2}"/>
  <rect x="16" y="98" width="120" height="12" rx="6" fill="{D}"/>
  <rect x="58" y="70" width="56" height="28" rx="5" fill="{D}"/>
  <rect x="58" y="78" width="56" height="5" fill="{W}" opacity="0.6"/>
  <rect x="58" y="87" width="56" height="5" fill="{W}" opacity="0.4"/>
</g>'''))

ICONS.append(("info", "#4FC3E8", "#1B6FB8", f'''
<g transform="translate(40 46)">
  <rect x="0" y="0" width="160" height="122" rx="18" fill="{W}"/>
  <path d="M22 88 A58 58 0 0 1 138 88" fill="none" stroke="{D}" stroke-width="14" stroke-linecap="round"/>
  <path d="M22 88 A58 58 0 0 1 84 30" fill="none" stroke="{A2}" stroke-width="14" stroke-linecap="round"/>
  <circle cx="80" cy="88" r="10" fill="{D}"/>
  <rect x="76" y="44" width="8" height="40" rx="4" fill="#2A57D4" transform="rotate(28 80 88)"/>
  <rect x="34" y="102" width="92" height="10" rx="5" fill="{D}"/>
</g>
<circle cx="196" cy="52" r="12" fill="{A}"/>'''))

ICONS.append(("security", "#5D8BF4", "#25309A", f'''
<path d="M120 34 L188 58 C188 128 160 176 120 200 C80 176 52 128 52 58 Z" fill="{W}"/>
<path d="M120 66 C96 66 76 84 68 100 C76 116 96 134 120 134 C144 134 164 116 172 100 C164 84 144 66 120 66 Z" fill="#2B3A9E"/>
<circle cx="120" cy="100" r="16" fill="{A2}"/>
<circle cx="120" cy="100" r="7" fill="{W}"/>'''))

ICONS.append(("maint", "#35C4A8", "#0C7364", f'''
<g transform="translate(96 128)">{gear(0, 0, 44, W, "#0C7364")}</g>
<g transform="rotate(38 96 128)">
  <rect x="88" y="44" width="17" height="96" rx="8" fill="{D}"/>
  <path d="M74 46 L74 26 h10 v12 h14 v-12 h10 v20 a22 22 0 0 1 -44 0 Z" fill="{D}"/>
</g>
<circle cx="188" cy="56" r="12" fill="{A2}"/>'''))

ICONS.append(("law", "#8E7BE8", "#422E96", f'''
<g transform="translate(0 6)">
  <rect x="114" y="46" width="12" height="118" rx="6" fill="{W}"/>
  <rect x="62" y="52" width="116" height="11" rx="5.5" fill="{W}"/>
  <rect x="86" y="164" width="68" height="14" rx="7" fill="{W}"/>
  <path d="M62 60 L36 108 L88 108 Z" fill="{D}"/>
  <path d="M178 60 L152 108 L204 108 Z" fill="{D}"/>
  <path d="M30 108 A34 22 0 0 0 94 108 Z" fill="{W}"/>
  <path d="M146 108 A34 22 0 0 0 210 108 Z" fill="{W}"/>
  <circle cx="120" cy="40" r="11" fill="{A2}"/>
</g>'''))

ICONS.append(("gege", "#E86FB4", "#9C2568", f'''
<g transform="translate(46 52)">
  <path d="M20 62 L28 8 L54 34 L74 0 L94 34 L120 8 L128 62 Z" fill="{W}"/>
  <rect x="16" y="66" width="116" height="16" rx="8" fill="{D}"/>
  <g transform="translate(26 92) rotate(-6)">
    <rect x="0" y="0" width="100" height="60" rx="8" fill="{D}"/>
    <rect x="12" y="14" width="60" height="7" rx="3.5" fill="{W}"/>
    <rect x="12" y="28" width="76" height="7" rx="3.5" fill="{W}"/>
    <rect x="12" y="42" width="44" height="7" rx="3.5" fill="{W}"/>
  </g>
</g>
<circle cx="186" cy="60" r="12" fill="{A2}"/>'''))

ICONS.append(("health", "#3CC98B", "#0B7C55", f'''
{heart(120, 118, 1.2, W)}
<path d="M120 44 L152 56 V110 C152 140 136 160 120 172 C104 160 88 140 88 110 V56 Z" fill="none" stroke="{D}" stroke-width="7" opacity="0.9"/>
<path d="M74 118 h18 l10 -18 l12 34 l10 -22 l8 6 h24" fill="none" stroke="#0B7C55" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>'''))

ICONS.append(("health-doudou", "#8BD95E", "#3B8F2A", f'''
{heart(104, 112, 1.05, W)}
<g transform="translate(126 116)"><rect x="0" y="0" width="76" height="76" rx="14" fill="{D}"/>
<path d="M16 40 l16 16 l28 -32" fill="none" stroke="#3B8F2A" stroke-width="11" stroke-linecap="round" stroke-linejoin="round"/></g>
<circle cx="186" cy="54" r="11" fill="{A2}"/>'''))

ICONS.append(("health-wife", "#F58FB4", "#B02063", f'''
{heart(122, 116, 1.3, W)}
<g transform="translate(122 118) scale(0.98)">
  <g fill="{A}">
    <ellipse cx="0" cy="-30" rx="15" ry="19"/><ellipse cx="29" cy="-9" rx="15" ry="19" transform="rotate(72 29 -9)"/>
    <ellipse cx="18" cy="25" rx="15" ry="19" transform="rotate(144 18 25)"/>
    <ellipse cx="-18" cy="25" rx="15" ry="19" transform="rotate(216 -18 25)"/>
    <ellipse cx="-29" cy="-9" rx="15" ry="19" transform="rotate(288 -29 -9)"/>
  </g>
  <circle cx="0" cy="0" r="12" fill="{A2}"/>
</g>'''))

ICONS.append(("health-mom", "#F2A65A", "#B85617", f'''
{heart(112, 126, 1.15, W)}
<path d="M118 40 L150 60 V96 H86 V60 Z" fill="{D}"/>
<rect x="108" y="78" width="20" height="18" rx="4" fill="{A2}"/>
<path d="M96 44 h44 l-22 -16 Z" fill="{W}"/>
<circle cx="188" cy="58" r="12" fill="{A}"/>'''))

ICONS.append(("company1", "#4C8BF5", "#1B47B0", f'''
<rect x="88" y="42" width="64" height="154" rx="10" fill="{W}"/>
<g fill="#1B47B0">
  <rect x="102" y="58" width="14" height="12" rx="3"/><rect x="126" y="58" width="14" height="12" rx="3"/>
  <rect x="102" y="82" width="14" height="12" rx="3"/><rect x="126" y="82" width="14" height="12" rx="3"/>
  <rect x="102" y="106" width="14" height="12" rx="3"/><rect x="126" y="106" width="14" height="12" rx="3"/>
</g>
<rect x="118" y="20" width="7" height="26" rx="3.5" fill="{W}"/>
<path d="M125 22 l30 9 l-30 9 Z" fill="{A2}"/>
<rect x="66" y="150" width="108" height="46" rx="10" fill="{D}"/>
<g fill="#4C8BF5"><rect x="80" y="164" width="14" height="12" rx="3"/><rect x="104" y="164" width="14" height="12" rx="3"/><rect x="128" y="164" width="14" height="12" rx="3"/></g>
<rect x="60" y="196" width="120" height="12" rx="6" fill="{D}"/>'''))

ICONS.append(("company2", "#F2A33C", "#B9620C", f'''
<rect x="52" y="70" width="58" height="126" rx="10" fill="{D}"/>
<g fill="#B9620C"><rect x="64" y="86" width="12" height="11" rx="3"/><rect x="84" y="86" width="12" height="11" rx="3"/>
<rect x="64" y="108" width="12" height="11" rx="3"/><rect x="84" y="108" width="12" height="11" rx="3"/>
<rect x="64" y="130" width="12" height="11" rx="3"/><rect x="84" y="130" width="12" height="11" rx="3"/></g>
<rect x="116" y="40" width="66" height="156" rx="10" fill="{W}"/>
<g fill="#B9620C"><rect x="130" y="56" width="14" height="12" rx="3"/><rect x="154" y="56" width="14" height="12" rx="3"/>
<rect x="130" y="80" width="14" height="12" rx="3"/><rect x="154" y="80" width="14" height="12" rx="3"/>
<rect x="130" y="104" width="14" height="12" rx="3"/><rect x="154" y="104" width="14" height="12" rx="3"/></g>
<g transform="translate(80 166)"><circle cx="0" cy="0" r="24" fill="{A2}"/>
<g fill="#B9620C"><rect x="-4" y="-34" width="8" height="14" rx="3"/><rect x="-4" y="20" width="8" height="14" rx="3"/>
<rect x="-34" y="-4" width="14" height="8" rx="3"/><rect x="20" y="-4" width="14" height="8" rx="3"/></g>
<circle cx="0" cy="0" r="9" fill="#B9620C"/></g>
<rect x="48" y="196" width="142" height="12" rx="6" fill="{D}"/>'''))

ICONS.append(("company3", "#6C63D8", "#372A8E", f'''
<rect x="40" y="96" width="52" height="100" rx="9" fill="{D}"/>
<g fill="#372A8E"><rect x="52" y="110" width="12" height="11" rx="3"/><rect x="70" y="110" width="12" height="11" rx="3"/>
<rect x="52" y="132" width="12" height="11" rx="3"/><rect x="70" y="132" width="12" height="11" rx="3"/></g>
<rect x="98" y="56" width="60" height="140" rx="10" fill="{W}"/>
<g fill="#372A8E"><rect x="112" y="72" width="13" height="12" rx="3"/><rect x="134" y="72" width="13" height="12" rx="3"/>
<rect x="112" y="96" width="13" height="12" rx="3"/><rect x="134" y="96" width="13" height="12" rx="3"/>
<rect x="112" y="120" width="13" height="12" rx="3"/><rect x="134" y="120" width="13" height="12" rx="3"/></g>
<rect x="162" y="118" width="44" height="78" rx="9" fill="{D}"/>
<g transform="translate(152 158)"><rect x="0" y="0" width="40" height="32" rx="6" fill="{A2}"/>
<rect x="9" y="-10" width="22" height="12" rx="4" fill="{W}"/></g>
<rect x="36" y="196" width="170" height="12" rx="6" fill="{D}"/>'''))

ICONS.append(("paike", "#4FA3F7", "#145FAE", f'''
<g transform="translate(46 52)">
  <rect x="0" y="16" width="148" height="126" rx="16" fill="{W}"/>
  <rect x="0" y="16" width="148" height="30" rx="16" fill="{D}"/>
  <rect x="24" y="2" width="14" height="26" rx="7" fill="{W}"/>
  <rect x="110" y="2" width="14" height="26" rx="7" fill="{W}"/>
  <g transform="translate(100 110)"><circle cx="0" cy="0" r="34" fill="{A}"/>
  <circle cx="0" cy="0" r="24" fill="#145FAE"/>
  <path d="M0 -13 V0 L11 8" stroke="{W}" stroke-width="6" fill="none" stroke-linecap="round"/></g>
  <rect x="20" y="62" width="46" height="9" rx="4.5" fill="{D}"/>
  <rect x="20" y="82" width="34" height="9" rx="4.5" fill="{D}"/>
</g>
<circle cx="196" cy="52" r="11" fill="{A2}"/>'''))

ICONS.append(("agant", "#7C6CF0", "#3B22A8", f'''
<g transform="translate(44 56)">
  <path d="M0 24 C26 10 58 10 76 22 C94 10 126 10 152 24 L152 118 C126 104 94 104 76 116 C58 104 26 104 0 118 Z" fill="{W}"/>
  <rect x="72" y="20" width="8" height="100" rx="4" fill="{D}"/>
  <g transform="translate(96 40)"><rect x="0" y="0" width="68" height="46" rx="12" fill="{A}"/>
  <path d="M14 46 l14 16 l4 -16 Z" fill="{A}"/>
  <rect x="14" y="16" width="40" height="7" rx="3.5" fill="{A2}"/></g>
</g>'''))

ICONS.append(("work", "#54B463", "#1B6B30", f'''
<g transform="translate(42 78)">
  <rect x="8" y="34" width="148" height="86" rx="14" fill="{W}"/>
  <rect x="8" y="34" width="148" height="18" rx="9" fill="{D}"/>
  <path d="M52 34 v-14 a12 12 0 0 1 12 -12 h32 a12 12 0 0 1 12 12 v14" fill="none" stroke="{D}" stroke-width="12" stroke-linecap="round"/>
  <rect x="70" y="62" width="24" height="26" rx="5" fill="{A2}"/>
  <rect x="8" y="76" width="148" height="9" rx="4.5" fill="{D}" opacity="0.75"/>
</g>
<circle cx="190" cy="54" r="12" fill="{A}"/>'''))

ICONS.append(("hermess", "#FF7A45", "#CE340F", f'''
<g transform="translate(46 56)">
  <rect x="0" y="0" width="148" height="124" rx="14" fill="{W}"/>
  <g stroke="{D}" stroke-width="5" stroke-linecap="round">
    <path d="M16 30 H132"/><path d="M16 46 H132"/><path d="M16 62 H132"/><path d="M16 78 H132"/><path d="M16 94 H132"/></g>
  <circle cx="46" cy="86" r="14" fill="#CE340F"/>
  <path d="M60 86 V38 l30 -8 v20" fill="none" stroke="#CE340F" stroke-width="7"/>
  <circle cx="120" cy="70" r="13" fill="#CE340F"/>
</g>
<path d="M188 40 l7 15 l16 2 l-12 11 l3 16 l-14 -8 l-14 8 l3 -16 l-12 -11 l16 -2 Z" fill="{A}"/>'''))

for key, c1, c2, body in ICONS:
    open(os.path.join(OUT, key + ".svg"), "w", encoding="utf-8").write(svg(key.replace("-", ""), c1, c2, body))
print("wrote", len(ICONS))
# -*- coding: utf-8 -*-
# 追加到 icon-forge.py：单图标（首字徽章）CLI 与关键词语义表
import sys as _sys
_KEYWORDS = {
 'health':'health','医疗':'health','健康':'health','print':'print3d','3d':'print3d','打印':'print3d',
 'video':'jianji','剪辑':'jianji','music':'hermess','乐谱':'hermess','作曲':'hermess','security':'security',
 '安保':'security','安全':'security','law':'law','法律':'law','company':'company1','公司':'company1',
 'info':'info','信息':'info','board':'info','news':'news_generic','新闻':'news_generic',
 'calendar':'paike','排课':'paike','日程':'paike','teach':'agant','老师':'agant','教育':'agant',
 'work':'work','干活':'work','tool':'work','工具':'work','maint':'maint','维护':'maint','backup':'backup_generic','备份':'backup_generic',
 'model':'model_generic','模型':'model_generic','project':'project_generic','项目':'project_generic',
 'cook':'cook_generic','厨师':'cook_generic','sport':'sport_generic','运动':'sport_generic',
}
_PALETTE = [('#5B9BFF','#2450C8'),('#F2A33C','#B9620C'),('#3CC98B','#0B7C55'),('#8E7BE8','#422E96'),
            ('#E86FB4','#9C2568'),('#4FC3E8','#1B6FB8'),('#FF8A5B','#D8342A'),('#35C4A8','#0C7364'),
            ('#6C63D8','#372A8E'),('#54B463','#1B6B30')]

def pick_colors(seed):
    h = sum(ord(c) for c in seed)
    return _PALETTE[h % len(_PALETTE)]

def monogram(name, c1, c2, out_png_dir="/home/j/.openclaw/workspace/state/icons/new"):
    import os
    ch = (name.strip() or '新')[0]
    body = ('<circle cx="120" cy="112" r="62" fill="#FFFFFF"/>'
            '<text x="120" y="112" text-anchor="middle" dominant-baseline="central" '
            'font-family="Noto Sans CJK SC, PingFang SC, Microsoft YaHei, sans-serif" '
            'font-size="76" font-weight="700" fill="' + c2 + '">' + ch + '</text>'
            '<circle cx="186" cy="58" r="12" fill="#FF9A2E"/>')
    key = 'new-' + (''.join(c for c in name if c.isalnum())[:12] or 'butler')
    path = os.path.join(out_png_dir, key + '.svg')
    open(path,'w',encoding='utf-8').write(svg(key.replace('-',''), c1, c2, body))
    return path

if __name__ == '__main__' and '--monogram' in _sys.argv:
    import json as _json
    i = _sys.argv.index('--monogram')
    nm = _sys.argv[i+1]
    c1, c2 = pick_colors(nm)
    pth = monogram(nm, c1, c2)
    print(_json.dumps({'svg': pth, 'name': nm, 'c1': c1, 'c2': c2}, ensure_ascii=False))
