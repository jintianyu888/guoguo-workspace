#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""self-improve.py — 每日自我提升：先量，再挑一件改（2026-11-12 主公令）

主公令：每天的任务就是不断找提升"稳定 / 智力 / 能力"的方法，给自己纠错和提效。
所以这个脚本不产出空话，只做三件事：
  1) 采集可量化指标（零 token）
  2) 与昨天/上周比，找"变差的那一项"
  3) 按预设规则给出今天的候选改进（排序，最多 3 条）

输出：state/improve/metrics-YYYYMMDD.json + 人读摘要
用法：python3 tools/self-improve.py [--json]
"""
import json, os, subprocess, sys, time, shutil

WS = '/home/j/.openclaw/workspace'
OUT = os.path.join(WS, 'state', 'improve')
os.makedirs(OUT, exist_ok=True)

def sh(cmd, timeout=40):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (p.stdout or '').strip()
    except Exception:
        return ''

def num(s, default=None):
    try:
        return float(s)
    except Exception:
        return default

def collect():
    m = {}
    m['ts'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    # 稳定性
    m['gateway_restarts'] = num(sh("systemctl --user show openclaw-gateway -p NRestarts --value"))
    m['gateway_active'] = sh("systemctl --user is-active openclaw-gateway")
    free = shutil.disk_usage('/')
    m['root_free_gb'] = round(free.free / 1e9, 1)
    m['shm_used_pct'] = num(sh("df --output=pcent /dev/shm | tail -1 | tr -d ' %'"))
    m['load1'] = num(sh("cut -d' ' -f1 /proc/loadavg"))
    # 网关健康（真实写探针由 health 体系负责，这里只看 HTTP）
    m['health'] = sh("curl -s -m 5 http://127.0.0.1:18789/health")[:40]
    # 节点
    try:
        nd = json.loads(sh("openclaw nodes list --json", 60) or '{}')
        now = time.time() * 1000
        ages = {}
        for n in nd.get('paired', []):
            last = n.get('lastConnectedAtMs') or 0
            disc = n.get('lastDisconnectedAtMs') or 0
            ref = disc if disc > last else last
            ages[n.get('displayName', '?')] = round((now - ref) / 60000, 1) if n.get('connected') is False else 0.0
        m['node_age_min'] = ages
    except Exception:
        m['node_age_min'] = {}
    # 账本
    t = sh("cd %s && python3 tools/tasks-db.py list 2>/dev/null" % WS)
    m['tasks_pending'] = sum(1 for l in t.splitlines() if '[pending' in l)
    m['tasks_in_progress'] = sum(1 for l in t.splitlines() if '[in_progress' in l)
    m['tasks_paused'] = sum(1 for l in t.splitlines() if '[paused' in l)
    # 错误账本
    try:
        mt = json.load(open(os.path.join(WS, 'state', 'decisions', 'mistakes.jsonl')))
        m['mistakes_total'] = len(mt) if isinstance(mt, list) else 0
    except Exception:
        m['mistakes_total'] = sum(1 for l in open(os.path.join(WS, 'state', 'decisions', 'mistakes.jsonl'), encoding='utf-8') if l.strip()) if os.path.exists(os.path.join(WS, 'state', 'decisions', 'mistakes.jsonl')) else 0
    # 哨兵状态
    for f, key in (('state/work/node-alive.json', 'stale_nodes'), ('state/work/exposure.json', 'fw_any')):
        p = os.path.join(WS, f)
        if os.path.exists(p):
            try:
                d = json.load(open(p))
                if key == 'stale_nodes':
                    m['stale_nodes'] = len(d.get('stale', []))
                else:
                    m['fw_any'] = len(d.get('firewall_open_any', {}) or {})
            except Exception:
                pass
    # 技能
    m['skills_unused_45d'] = num(sh("python3 tools/skill-usage.py stale 2>/dev/null | tail -1")) 
    return m

BASELINE = os.path.join(OUT, 'baseline.json')

def candidates(m, base):
    c = []
    if m.get('stale_nodes'):
        c.append((90, '节点掉线未恢复：%s' % m['node_age_min'], '排查掉线节点（先看是休眠还是进程死）'))
    if m.get('node_age_min') and any(v and v > 120 for v in m['node_age_min'].values()):
        c.append((80, '有节点超过 2 小时没连：%s' % m['node_age_min'], '查该机 Task/Startup 是否失效'))
    if m.get('gateway_restarts') and base.get('gateway_restarts') is not None and m['gateway_restarts'] > base['gateway_restarts']:
        c.append((70, '网关重启次数增加 %d → %d' % (base['gateway_restarts'], m['gateway_restarts']), '查重启根因，别用重启掩盖'))
    if m.get('root_free_gb') is not None and m['root_free_gb'] < 40:
        c.append((65, '根分区剩余仅 %.1fG' % m['root_free_gb'], '清缓存/查快照残留'))
    if m.get('shm_used_pct') is not None and m['shm_used_pct'] > 60:
        c.append((60, '/dev/shm 使用 %s%%' % m['shm_used_pct'], '查浏览器/快照残留，必要时清'))
    if m.get('tasks_pending', 0) + m.get('tasks_in_progress', 0) > 6:
        c.append((55, '未结任务 %d 条，超过 6 条上限' % (m['tasks_pending'] + m['tasks_in_progress']), '合并/冻结/关单'))
    if m.get('fw_any'):
        c.append((50, '防火墙存在任何IP放行 %d 条' % m['fw_any'], '按暴露面哨兵处理'))
    if m.get('health') and 'ok' not in m.get('health', ''):
        c.append((88, '网关健康探测异常：%s' % m.get('health'), '先止血再复盘'))
    c.sort(reverse=True)
    return c[:3]

def main():
    m = collect()
    base = {}
    if os.path.exists(BASELINE):
        try: base = json.load(open(BASELINE))
        except Exception: base = {}
    json.dump(m, open(os.path.join(OUT, 'metrics-%s.json' % time.strftime('%Y%m%d')), 'w'), ensure_ascii=False, indent=1)
    human = []
    human.append('== 今日指标 %s ==' % m['ts'])
    human.append('网关：%s · 重启累计 %s · 健康 %s' % (m.get('gateway_active'), m.get('gateway_restarts'), (m.get('health') or '')[:20]))
    human.append('磁盘：根 %sG 空闲 · /dev/shm %s%% · load1 %s' % (m.get('root_free_gb'), m.get('shm_used_pct'), m.get('load1')))
    human.append('节点：%s' % (m.get('node_age_min') or '未取到'))
    human.append('任务：pending %s · in_progress %s · paused %s' % (m.get('tasks_pending'), m.get('tasks_in_progress'), m.get('tasks_paused')))
    human.append('错误账本累计 %s 条' % m.get('mistakes_total'))
    cs = candidates(m, base)
    human.append('')
    if cs:
        human.append('== 今日候选改进（按影响排序，今天挑一件做到底）==')
        for pri, why, act in cs:
            human.append('[%d] %s → 动作：%s' % (pri, why, act))
    else:
        human.append('== 今日无退化项：那今天做"能力"而非"稳定"——升级一个薄弱环节的自动化 ==')
    # 基线：每周一刷新，避免天天比烂
    if time.localtime().tm_wday == 0 or not base:
        json.dump(m, open(BASELINE, 'w'), ensure_ascii=False, indent=1)
        human.append('（已刷新周基线）')
    print(chr(10).join(human))
    return 0

if __name__ == '__main__':
    sys.exit(main())
