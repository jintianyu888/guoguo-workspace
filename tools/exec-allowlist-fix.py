
import json, subprocess, os, sys, shutil, time
CLI='/home/j/.npm-global/bin/openclaw'
APPLY = '--apply' in sys.argv
cfg = json.loads(subprocess.run([CLI,'config','get','agents'],capture_output=True,text=True).stdout)
entries = cfg.get('entries', {})
FLAG_PROFILE = {'allowedValueFlags':['--no','--did','--next','--by','--task','--note'],'deniedFlags':[],'maxPositional':0}
TRUST = ['/home/j/.openclaw/workspace/tools']
changed=[]
for aid, a in entries.items():
    tools = a.get('tools') or {}
    e = (tools.get('exec') or {})
    if not e or e.get('mode') != 'allowlist':
        continue
    bins = list(e.get('safeBins') or [])
    prof = dict(e.get('safeBinProfiles') or {})
    orig = (list(bins), dict(prof), list(e.get('safeBinTrustedDirs') or []))
    newbins=[]
    for b in bins:
        if '/' in b:
            base=os.path.basename(b)
            if base not in newbins: newbins.append(base)
            prof.setdefault(base,{})
        else:
            if b not in newbins: newbins.append(b)
    for s in ['model-footer.py','agent-msg.sh','completion-notify.sh','notify.sh','butler-save.sh','butler-fact-pack.sh','maint-report-save.sh','fetch-web.sh','proxy-env.sh']:
        if s not in newbins: newbins.append(s)
        prof.setdefault(s,{})
    prof['completion-notify.sh']=FLAG_PROFILE
    dirs=[d for d in (e.get('safeBinTrustedDirs') or [])]
    for t in TRUST:
        if t not in dirs: dirs.append(t)
    if (newbins,prof,dirs)!=orig:
        e['safeBins']=newbins; e['safeBinProfiles']=prof; e['safeBinTrustedDirs']=dirs
        tools['exec']=e; a['tools']=tools
        changed.append(aid)
print('需要修的管家:', len(changed), changed[:20])
if not APPLY:
    print('dry-run，未写入；加 --apply 生效'); raise SystemExit(0)
stamp=time.strftime('%Y%m%d-%H%M%S')
bk=f'/home/j/.openclaw/workspace/state/backup/config/openclaw.json.bak-execallow-{stamp}'
shutil.copy('/home/j/.openclaw/openclaw.json', bk)
print('备份:', bk)
ok=fail=0
for aid in changed:
    d=json.loads(subprocess.run([CLI,'config','get',f'agents.entries.{aid}'],capture_output=True,text=True).stdout)
    p=subprocess.run([CLI,'config','set',f'agents.entries.{aid}',json.dumps(d,ensure_ascii=False),'--strict-json'],capture_output=True,text=True)
    if p.returncode==0: ok+=1
    else: fail+=1; print('FAIL',aid,(p.stderr or '')[:120])
print(f'已修 {ok}，失败 {fail}')
