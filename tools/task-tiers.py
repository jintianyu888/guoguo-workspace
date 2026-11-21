#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""task-tiers.py —— 把所有 cron 任务与 systemd 定时器分 L0–L3 并出清单（L=Level 级别；T1/T2 仅作"备份类型"专名，不表示级别）。
L0 生命线：停了就瞎/丢数据的前置守护（秒级、全天）
L1 数据与安全：备份/哈希/镜像/演练/杀毒/安防（重活，仅夜间窗）
L2 日常运营：简报/自审/汇总/账本/体检/监控/审计
L3 可延后：月报/年结/优化建议/索引刷新/雷达/评审/清理整理
用法: python3 tools/task-tiers.py [--write]   --write 同时写 docs/任务分级清单-YYYYMMDD.md
"""
import json, os, re, subprocess, sqlite3, datetime, sys

W = '/home/j/.openclaw/workspace'
NOW = datetime.datetime.now()

T0 = re.compile(r'看门狗|watchdog|心跳|heartbeat|失败哨兵|备份安全告警|网络保险|节点存活|存活|guard|峰时|peak|静默兜底|sentinel|监控')
T1b = re.compile(r'mirror|backup|face|security|retain')
T1 = re.compile(r'全量备份|T1|T2|哈希|镜像|恢复演练|drill|杀毒|安全扫描|安防|巡逻|云端加密|保留|retention|备份|镜像校验|一致性|归档')
T3 = re.compile(r'月报|月度|年结|雷达|radar|评审|review|索引刷新|探活|优化|建议|清理|整理|盘点|盲区|闲置|评分|archive|审计|janitor|cache|trash|purge|clean')

def tier(name, body):
    s = name + ' ' + body
    if T0.search(name): return 'L0'
    if re.search(r'自审|互审|自检', name): return 'L2'   # 自审类不因名字里带 backup 而升级
    if T1.search(name) or T1b.search(name): return 'L1'
    if T3.search(name): return 'L3'
    return 'L2'

def avg_secs(con, name):
    r = con.execute("select avg(seconds),max(seconds),count(*) from runs where name=? and status='ok'", (name,)).fetchone()
    return int(r[0] or 0), int(r[1] or 0), int(r[2] or 0)

def main():
    jobs = json.loads(subprocess.run(['openclaw','cron','list','--json'], capture_output=True, text=True, timeout=120).stdout)
    js = jobs.get('jobs') or jobs
    con = sqlite3.connect(os.path.join(W,'state/ledger/jobs.db'))
    rows = []
    for j in js:
        if not j.get('enabled'): continue
        p = j.get('payload') or {}
        body = str(p.get('argv') or p.get('message') or '')
        a, mx, n = avg_secs(con, j.get('name'))
        rows.append(dict(t=tier(j.get('name'), body), sched=(j.get('schedule') or {}).get('expr',''),
                         name=j.get('name'), kind=p.get('kind',''), avg=a, max=mx, runs=n, src='cron'))
    # systemd timers
    out = subprocess.run(['systemctl','--user','list-timers','--all','--no-pager'], capture_output=True, text=True).stdout
    for line in out.splitlines()[1:]:
        m = re.search(r'(\S+\.timer)\s+(\S+)\s*$', line)
        if not m: continue
        unit = m.group(1)
        name = unit.replace('.timer','')
        sched_m = re.match(r'^(\S+\s+\S+\s+\S+|\S+)\s', line)
        rows.append(dict(t=tier(name,''), sched='systemd', name=name, kind='timer', avg=0, max=0, runs=0, src='timer'))
    rows.sort(key=lambda r: (r['t'], r['sched'], r['name']))
    order = {'L0':0,'L1':1,'L2':2,'L3':3}
    lines = []
    cnt = {}
    for r in rows: cnt[r['t']] = cnt.get(r['t'],0)+1
    lines.append('# 任务分级清单 L0–L3（%s 生成）\n' % NOW.strftime('%Y-%m-%d %H:%M'))
    lines.append('口径：L0 生命线｜L1 数据与安全（重活仅 00:30–07:30）｜L2 日常运营｜L3 可延后\n')
    lines.append('总计 %d 项：%s\n' % (len(rows), '／'.join('%s %d' % (k, cnt[k]) for k in ['L0','L1','L2','L3'] if k in cnt)))
    desc = {'L0':'生命线（全天，秒级）','L1':'数据与安全（重活仅夜间窗）','L2':'日常运营','L3':'可延后/低价值'}
    for lv in ['L0','L1','L2','L3']:
        lines.append('\n## %s %s\n' % (lv, desc[lv]))
        lines.append('| 时间 | 名称 | 类型 | 平均耗时 | 说明 |')
        lines.append('|---|---|---|---|---|')
        for r in [x for x in rows if x['t']==lv]:
            a = ('%d 分' % (r['avg']//60)) if r['avg']>=60 else ('%d 秒' % r['avg'] if r['avg'] else '—')
            lines.append('| %s | %s | %s | %s | %s |' % (r['sched'], r['name'], r['kind'], a, ('近 30 天 %d 次' % r['runs']) if r['runs'] else '无运行记录'))
    doc = '\n'.join(lines) + '\n'
    print(doc[:1500])
    if '--write' in sys.argv:
        p = os.path.join(W, 'docs/任务分级清单-%s.md' % NOW.strftime('%Y%m%d'))
        open(p,'w',encoding='utf-8').write(doc)
        print('WROTE', p)
        open('/tmp/tiers.json','w').write(json.dumps(rows, ensure_ascii=False))
    print('COUNTS', cnt)

if __name__ == '__main__':
    main()
