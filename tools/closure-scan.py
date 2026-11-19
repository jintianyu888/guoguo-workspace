#!/usr/bin/env python3
# closure-scan.py - find done items closed without independent verification. Read-only, zero token.
import json, sqlite3, sys, time

DB = '/home/j/.openclaw/workspace/state/tasks/tasks.db'
PROP = '/home/j/.openclaw/workspace/state/approvals/proposals.jsonl'
days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
cut = time.strftime('%Y-%m-%d', time.localtime(time.time() - days * 86400))

c = sqlite3.connect('file:' + DB + '?mode=ro', uri=True)
rows = c.execute("select no,title,status,who,closed_by,verify,updated from tasks where status='done' and substr(updated,1,10)>=?", (cut,)).fetchall()
self_closed = [r for r in rows if (r[4] or '').strip() and (r[3] or '').strip() and r[4].strip() == r[3].strip()]
no_verify = [r for r in rows if not (r[5] or '').strip()]
no_closer = [r for r in rows if not (r[4] or '').strip()]

print('window: last %d days (since %s)' % (days, cut))
print('done: %d | no verify: %d | no closed_by: %d | self-closed: %d' % (len(rows), len(no_verify), len(no_closer), len(self_closed)))
for tag, lst in (('NO_VERIFY', no_verify), ('SELF_CLOSED', self_closed)):
    for r in lst[:15]:
        print('  %s #%s %s | who=%s closed_by=%s' % (tag, r[0], (r[1] or '')[:40], r[3] or '-', r[4] or '-'))

try:
    items = [json.loads(l) for l in open(PROP, encoding='utf-8') if l.strip()]
except Exception as e:
    items = []
    print('proposals unreadable:', e)
stale = [i for i in items if (i.get('status') or '') == 'approved' and not (i.get('note') or '').strip()]
open_new = [i for i in items if (i.get('status') or 'new') == 'new']
print('proposals: total %d | new %d | approved-without-note %d' % (len(items), len(open_new), len(stale)))
for i in open_new[:10]:
    print('  NEW %s %s' % (i.get('id'), (i.get('title') or i.get('text') or '')[:70]))

