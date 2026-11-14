#!/usr/bin/env python3
# senate-pack.py - build the evidence pack a senator audits. Read-only, zero token.
import glob, json, os, subprocess, sys, time

WS = '/home/j/.openclaw/workspace'
OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/senate-pack.md'
CAP = 80000

def sh(cmd, timeout=90):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or '')
        if r.stderr and r.stderr.strip():
            out += '\n[stderr] ' + r.stderr.strip()[:400]
        return out
    except Exception as e:
        return '[ERROR] ' + str(e)[:200]

def cutoff(hours):
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(time.time() - hours * 3600))

parts = []
parts.append('# Evidence pack (raw artifacts, no self-assessment)')
parts.append('generated: ' + time.strftime('%Y-%m-%d %H:%M:%S %Z'))

wl = os.path.join(WS, 'state/log/worklog.jsonl')
rows = []
if os.path.exists(wl):
    c = cutoff(24)
    for line in open(wl, encoding='utf-8', errors='replace'):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        ts = str(d.get('ts') or d.get('time') or '')
        if ts >= c:
            rows.append(line)
parts.append('\n## 1. Worklog last 24h (%d entries)\n```jsonl\n%s\n```' % (len(rows), '\n'.join(rows[-250:])))

parts.append('\n## 2. Open tasks (tasks.db)\n```\n' + sh('cd ' + WS + ' && python3 tools/tasks-db.py list 2>&1 | head -120') + '\n```')
parts.append('\n## 3. Proposals digest\n```\n' + sh('cd ' + WS + ' && python3 tools/steward-proposals.py digest 2>&1 | head -80') + '\n```')
parts.append('\n## 4. Restart log tail\n```\n' + sh('tail -25 ' + WS + '/state/work/safe-restart.log 2>&1') + '\n```')
parts.append('\n## 5. Failed systemd units\n```\n' + sh('systemctl --user --failed --no-pager 2>&1 | head -30') + '\n```')
parts.append('\n## 6. Recent alerts\n```\n' + sh('tail -40 ' + WS + '/state/alert/*.log 2>/dev/null') + '\n```')

sr = []
for p in glob.glob('/home/j/openclaw-workspaces/*/state/self-review/*'):
    if time.time() - os.path.getmtime(p) < 28 * 3600:
        sr.append(p)
sr.sort()
chunks = []
for p in sr[-12:]:
    try:
        body = open(p, encoding='utf-8', errors='replace').read()[:2500]
    except Exception as e:
        body = '[unreadable] ' + str(e)
    chunks.append('### ' + p + '\n' + body)
parts.append('\n## 7. Butler self-reviews (last 28h, %d files)\n%s' % (len(sr), '\n\n'.join(chunks) if chunks else '(none)'))

cronpy = "import sys,json;d=json.load(sys.stdin);j=d if isinstance(d,list) else d.get('jobs',[]);bad=[x for x in j if (x.get('lastDeliveryStatus') or '') in ('not-requested','failed')];print(len(j),'jobs',len(bad),'not delivering');[print(' -',x.get('name'),x.get('lastDeliveryStatus')) for x in bad[:20]]"
parts.append('\n## 8. Scheduled job delivery status\n```\n' + sh('/home/j/.npm-global/bin/openclaw cron list --json 2>/dev/null | python3 -c "' + cronpy + '"') + '\n```')

text = '\n'.join(parts)
parts.append('\n## 9. Closure holes (done without independent verify)\n```\n' + sh('cd ' + WS + ' && python3 tools/closure-scan.py 7 2>&1 | head -40') + '\n```')

text = '\n'.join(parts)
if len(text) > CAP:
    text = text[:CAP] + '\n\n[TRUNCATED at %d chars]' % CAP
open(OUT, 'w', encoding='utf-8').write(text)
print('pack', OUT, len(text), 'chars')

