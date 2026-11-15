#!/usr/bin/env python3
"""检查所有 allowlist 管家是否都装了「通用只读工具集」（果果 2026-11-15 A 方案）。"""
import json,os,sys
CFG=os.path.expanduser('~/.openclaw/openclaw.json')
COMMON={'curl','wget','tar','unzip','xz','python3','git','ffmpeg','yt-dlp','7zz','rsync','pdftotext',
        'fetch-web.sh','proxy-env.sh','jq'}
d=json.load(open(CFG))
bad=[]
for aid,e in (d.get('agents',{}).get('entries') or {}).items():
    ex=(e.get('tools',{}) or {}).get('exec') or {}
    if ex.get('mode')!='allowlist': continue
    have={os.path.basename(str(b)) for b in (ex.get('safeBins') or [])}
    lack=sorted(COMMON-have)
    if lack: bad.append((aid,lack))
if not bad:
    print('OK 通用工具集齐全')
    sys.exit(0)
for aid,lack in bad:
    print(f'{aid} 缺: {",".join(lack)}')
sys.exit(1)
