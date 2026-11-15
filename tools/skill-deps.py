#!/usr/bin/env python3
"""skill-deps.py —— 技能「能用」体检（共享可见 ≠ 有权限执行）。
默认：每个技能一行，报需要哪些命令、多少管家真能跑。
用法：
  python3 tools/skill-deps.py             # 汇总
  python3 tools/skill-deps.py --agent print   # 只看某个管家缺什么
  python3 tools/skill-deps.py --need      # 只列有缺口的技能
"""
import json,os,re,sys,glob
CFG=os.path.expanduser('~/.openclaw/openclaw.json')
SKILLS=os.path.expanduser('~/.openclaw/shared-skills')
KNOWN=['curl','wget','yt-dlp','python3','jq','ffmpeg','7zz','unzip','tar','xz','pdftoppm',
       'img2pdf','gs','qpdf','magick','convert','rsync','ssh','git','node','npm','sqlite3',
       'nvidia-smi','adb','rclone','pdftotext','soffice']
def bins_in(text):
    return {b for b in KNOWN if re.search(r'(?<![\w-])'+re.escape(b)+r'(?![\w-])', text)}
def agents():
    d=json.load(open(CFG)); out={}
    for aid,e in (d.get('agents',{}).get('entries') or {}).items():
        ex=(e.get('tools',{}) or {}).get('exec',{}) or {}
        mode=ex.get('mode') or 'full'
        if mode!='allowlist':
            out[aid]=set(KNOWN)
        else:
            out[aid]=set(os.path.basename(str(b)) for b in (ex.get('safeBins') or []))
    return out
def main():
    ag=agents(); args=sys.argv[1:]
    only_need='--need' in args
    target=None
    if '--agent' in args:
        target=args[args.index('--agent')+1]
    rows=[]
    for p in sorted(glob.glob(os.path.join(SKILLS,'*','SKILL.md'))):
        name=os.path.basename(os.path.dirname(p))
        need=bins_in(open(p,encoding='utf-8',errors='ignore').read())
        if not need: continue
        ok=[a for a,b in ag.items() if need<=b]
        rows.append((name,sorted(need),ok))
    if target:
        t=ag.get(target)
        if t is None: print(f'没有 {target} 的 allowlist 配置'); return 1
        print(f'{target} 缺命令的技能：\n')
        n=0
        for name,need,ok in rows:
            lack=sorted(set(need)-t)
            if lack:
                n+=1; print(f'- {name}: 缺 {",".join(lack)}')
        print(f'\n合计 {n} 个技能跑不了。修法：加进 agents.entries.{target}.tools.exec 的 safeBins 与 safeBinProfiles（两者缺一不生效）。')
        return 1 if n else 0
    print('技能「能用」体检（ALL=有 allowlist 的管家数）\n')
    gaps=0
    for name,need,ok in rows:
        full=len(ok)==len(ag)
        if only_need and full: continue
        gaps += 0 if full else 1
        flag='✅' if full else '⚠️'
        print(f'{flag} {name}  需要 {",".join(need)}  → {len(ok)}/{len(ag)} 家可跑')
    print(f'\n有缺口技能 {gaps}/{len(rows)}。看单个管家: --agent <id>；只看缺口: --need')
    return 0
if __name__=='__main__':
    sys.exit(main())
