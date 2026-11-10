#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''facts.py — 跨管家硬事实账本（state/facts/facts.db 为唯一真源）

只收「可枚举、机器要读、多家会冲突」的事实；叙述性记忆不进这里（走 butler-digest 周蒸馏）。
写入必须带 evidence（文件路径或命令）与 confirmed_by；无证据不入库。
命令：init | seed | add | set | get | list | stats | export-md | review
'''

import argparse, json, os, sqlite3, sys
from datetime import datetime

WS = '/home/j/.openclaw/workspace'
DB = os.path.join(WS, 'state', 'facts', 'facts.db')
MD = os.path.join(WS, 'docs', '事实账本-20261107.md')

DDL = '''
create table if not exists facts(
  id integer primary key autoincrement,
  domain text not null, key text not null, value text not null,
  source text, evidence text, status text default 'confirmed',
  confirmed_by text, confirmed_at text, updated_at text, note text,
  unique(domain, key));
create index if not exists ix_facts_domain on facts(domain);
'''


def conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript(DDL)
    return c


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def upsert(c, domain, key, value, evidence, source='', status='confirmed', by='agent', note=''):
    ts = now()
    c.execute('''insert into facts(domain,key,value,source,evidence,status,confirmed_by,confirmed_at,updated_at,note)
                 values(?,?,?,?,?,?,?,?,?,?)
                 on conflict(domain,key) do update set value=excluded.value, source=excluded.source,
                 evidence=excluded.evidence, status=excluded.status, confirmed_by=excluded.confirmed_by,
                 confirmed_at=excluded.confirmed_at, updated_at=excluded.updated_at, note=excluded.note''',
              (domain, key, value, source, evidence, status, by, ts, ts, note))


SEED = [
    ('设备与网络', 'gateway.port', '18789', 'AGENTS.md#本机运维要点', 'gateway 用户单元 openclaw-gateway，token 鉴权'),
    ('设备与网络', 'panel.port', '8899', 'AGENTS.md#本机运维要点', '果果助手面板 guoguo.service'),
    ('设备与网络', 'printer.ipp', 'http://192.168.1.80/ipp/print', 'docs/打印提速与提质清单-20261107.md', 'application/pdf；raw 9100 PS 会丢图'),
    ('设备与网络', 'printer.port', 'IPP 631', 'docs/打印提速与提质清单-20261107.md', '走 IPP 631，不走 9100'),
    ('设备与网络', 'printer.quality', 'print-quality=5', 'docs/打印提速与提质清单-20261107.md', '提速测试须逐变量记录'),
    ('设备与网络', 'nvr.ip', '192.168.1.103', 'MEMORY.md', 'Hikvision，16 通道；凭据在 /home/j/.config/hik-nvr.env'),
    ('设备与网络', 'nas.ip', '192.168.1.109', 'MEMORY.md', '新群晖；备份目标 /mnt/nas/archive/jinyu/openclaw-archives'),
    ('设备与网络', 'machineB.ollama', '192.168.1.107', 'MEMORY.md', 'B 机 ollama；A 机 11435 本地，11434 是代理'),
    ('排期与窗口', 'backup.full', '01:00', 'docs/时间表与窗口规则-20261031.md', '每日一次全量归档，不做第二次'),
    ('排期与窗口', 'backup.mirror', '03:50', 'docs/时间表与窗口规则-20261031.md', '镜像到 E/H/NAS'),
    ('排期与窗口', 'restart.window', '08:00', 'AGENTS.md#重启类任务的归属', '只走 tools/restart-gateway.sh，13 项自检'),
    ('排期与窗口', 'quiet.window', '04:00-06:05', 'MEMORY.md', '静默窗，告警排队 06:10 重放'),
    ('排期与窗口', 'peak.hours', '工作日 09-12 / 14-18', 'AGENTS.md#排工', 'token 类任务禁跑；周末与节假日半价'),
    ('排期与窗口', 'red.zones', '01:00-02:30 / 04:00-06:05 / 07:45-08:15', 'MEMORY.md', '任务排期避开'),
    ('额度与钱', 'model.econ', '以 tools/model-econ.sh 为准', 'AGENTS.md#成本', '余额/额度/价格不自行抓取换算'),
    ('权限与边界', 'gateway.restart', '仅 tools/restart-gateway.sh', 'AGENTS.md#重启类任务的归属', '禁止裸 systemctl / gateway 工具重启'),
    ('权限与边界', 'maint.mode', '只读，只出建议不落盘', 'AGENTS.md#四大管家', '告警唯一出口是果果警告'),
]


def cmd_seed(c):
    n = 0
    for dom, key, val, src, note in SEED:
        upsert(c, dom, key, val, evidence=src, source=src, by='agent(文档实证)', note=note)
        n += 1
    c.commit()
    print('seed 完成：%d 条（已存在则覆盖）' % n)


SENSITIVE = ('健康指标', '家庭硬信息', '权限与账号')


def cmd_add(c, a):
    if not a.evidence:
        print('拒绝：必须给 --evidence（文件路径或命令）')
        return 2
    if a.domain in SENSITIVE and (not a.by or a.by == 'agent'):
        print('拒绝：%s 属敏感域，需 --by 明确确认人（人工/双审）' % a.domain)
        return 3
    upsert(c, a.domain, a.key, a.value, a.evidence, a.source or a.evidence, a.status, a.by or 'agent', a.note or '')
    c.commit()
    print('已写入 %s / %s' % (a.domain, a.key))
    return 0


def cmd_get(c, a):
    for r in c.execute('select domain,key,value,evidence,status,updated_at from facts where key like ? or value like ?', ('%' + a.key + '%', '%' + a.key + '%')):
        print(' | '.join(str(x) for x in r))
    return 0


def cmd_list(c, a):
    q = 'select domain,key,value,status,updated_at from facts'
    args = ()
    if a.domain:
        q += ' where domain=?'
        args = (a.domain,)
    q += ' order by domain,key'
    for r in c.execute(q, args):
        print(' | '.join(str(x) for x in r))
    return 0


def cmd_stats(c):
    print('facts:', c.execute('select count(*) from facts').fetchone()[0])
    for dom, n, conf in c.execute("select domain,count(*),sum(status='confirmed') from facts group by domain order by 2 desc"):
        print('  %-12s %3d 条（已确认 %s）' % (dom, n, conf))
    return 0


def cmd_export(c):
    lines = ['# 事实账本（机器真源：state/facts/facts.db）', '', '更新：' + now(), '']
    cur = None
    for dom, key, val, ev, st, upd in c.execute('select domain,key,value,evidence,status,updated_at from facts order by domain,key'):
        if dom != cur:
            lines += ['', '## ' + dom, '']
            cur = dom
        lines.append('- **%s** = %s　（%s；%s；%s）' % (key, val, ev, st, upd))
    open(MD, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('导出 →', MD)
    return 0


def cmd_review(c):
    '列出候选清单里尚未入库的候选数（人工确认用）'
    import glob
    fs = sorted(glob.glob(os.path.join(WS, 'state', 'facts', 'candidates-*.md')))
    if not fs:
        print('无候选文件')
        return 0
    p = fs[-1]
    txt = open(p, encoding='utf-8').read()
    print('候选文件:', os.path.relpath(p, WS))
    for ln in txt.splitlines():
        if ln.startswith('## '):
            print(' ', ln[3:])
    print('已入库:', c.execute('select count(*) from facts').fetchone()[0], '条')
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init')
    sub.add_parser('seed')
    sub.add_parser('stats')
    sub.add_parser('export-md')
    sub.add_parser('review')
    p = sub.add_parser('add')
    p.add_argument('domain'); p.add_argument('key'); p.add_argument('value')
    p.add_argument('--evidence'); p.add_argument('--source'); p.add_argument('--status', default='confirmed')
    p.add_argument('--by'); p.add_argument('--note')
    p = sub.add_parser('get'); p.add_argument('key')
    p = sub.add_parser('list'); p.add_argument('--domain')
    a = ap.parse_args()
    c = conn()
    return {'init': lambda: (print('库就绪:', DB), 0)[1],
            'seed': lambda: (cmd_seed(c), 0)[1],
            'add': lambda: cmd_add(c, a),
            'get': lambda: cmd_get(c, a),
            'list': lambda: cmd_list(c, a),
            'stats': lambda: cmd_stats(c),
            'export-md': lambda: cmd_export(c),
            'review': lambda: cmd_review(c)}[a.cmd]()


if __name__ == '__main__':
    sys.exit(main())
