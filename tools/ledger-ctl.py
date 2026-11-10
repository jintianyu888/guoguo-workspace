#!/usr/bin/env python3
# ledger-ctl.py - single write entry for the ledger (graded + audited)
# L0 data registration: free, logged
# L1 schema/logic change: requires --review <dual-review file>
# L2 destructive: requires --review AND --owner-ok 1
import sqlite3, os, sys, time, hashlib
W = '/home/j/.openclaw/workspace'
DB = W + '/state/ledger/ledger.db'
def conn():
    c = sqlite3.connect(DB)
    c.execute('pragma journal_mode=WAL')
    return c
def init(c):
    c.execute('create table if not exists ledger_audit(id integer primary key autoincrement, ts int, grade text, action text, target text, detail text, operator text, review_file text, review_hash text)')
def grade(action):
    if action in ('delete', 'purge', 'cleanup', 'retention'):
        return 'L2'
    if action in ('schema', 'rekey', 'remap', 'rule'):
        return 'L1'
    return 'L0'
def main():
    if len(sys.argv) < 2:
        print('usage: ledger-ctl.py <action> [--target v] [--detail v] [--review file] [--owner-ok 1] [--operator name]')
        return 2
    action = sys.argv[1]
    args = {}
    i = 2
    while i + 1 < len(sys.argv):
        args[sys.argv[i]] = sys.argv[i + 1]
        i += 2
    g = grade(action)
    rf = args.get('--review', '')
    if g in ('L1', 'L2') and not (rf and os.path.exists(rf)):
        print('REFUSE: ' + action + ' is ' + g + ', needs --review <dual-review file>')
        return 3
    if g == 'L2' and args.get('--owner-ok') != '1':
        print('REFUSE: L2 also needs --owner-ok 1')
        return 3
    c = conn(); init(c)
    rh = hashlib.sha256(open(rf, 'rb').read()).hexdigest()[:16] if rf and os.path.exists(rf) else ''
    c.execute('insert into ledger_audit(ts,grade,action,target,detail,operator,review_file,review_hash) values(?,?,?,?,?,?,?,?)',
              (int(time.time()), g, action, args.get('--target', ''), args.get('--detail', ''), args.get('--operator', 'main'), rf, rh))
    c.commit()
    print('OK ' + action + ' grade=' + g + ' audited')
    return 0
sys.exit(main())