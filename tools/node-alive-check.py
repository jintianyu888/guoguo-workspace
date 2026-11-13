#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""node-alive-check.py — 节点活性哨兵（2026-11-12）

背景：2026-11-12 22:25 发现 C-Library 已断开 11 小时，计划任务里的 node 进程还在跑
（进程活着 != 连接活着），而 nobody 发现。这个哨兵补的就是这条缝。

判据：lastConnectedAtMs 距今 > STALE_MIN 分钟，或 lastDisconnectedAtMs 晚于 lastConnectedAtMs 且已超期。
动作：有超期节点 -> notify.sh 一条（同类 6 小时内只报一次）；明细写 state/work/node-alive.json
退出码：0 全部在期 / 1 有超期节点
"""
import json, os, shutil, subprocess, sys, time

WS = '/home/j/.openclaw/workspace'
STATE = os.path.join(WS, 'state', 'work', 'node-alive.json')
STALE_MIN = int(os.environ.get('NODE_STALE_MIN', '30'))
DEDUP_H = 6

OC_CANDIDATES = ('/home/j/.npm-global/bin/openclaw', '/home/j/.openclaw/tmp/agent-cli/openclaw')


def oc_bin():
    """systemd 用户单元里 PATH 不含 npm-global，直接写死候选绝对路径（2026-11-13 修）。"""
    for c in OC_CANDIDATES:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return shutil.which('openclaw') or 'openclaw'


def nodes():
    p = subprocess.run([oc_bin(), 'nodes', 'list', '--json'], capture_output=True, text=True, timeout=60)
    out = (p.stdout or '').strip()
    if p.returncode != 0 or not out:
        raise RuntimeError('openclaw nodes list failed rc=%s err=%s' % (p.returncode, (p.stderr or '')[:200]))
    return json.loads(out)['paired']

def main():
    st = {}
    if os.path.exists(STATE):
        try: st = json.load(open(STATE))
        except Exception: st = {}
    now = int(time.time() * 1000)
    stale, fresh = [], []
    for n in nodes():
        name = n.get('displayName') or n.get('nodeId', '')[:8]
        last = n.get('lastConnectedAtMs') or 0
        disc = n.get('lastDisconnectedAtMs') or 0
        connected = n.get('connected')
        # 关键修正（M-20261112-003）：lastConnectedAtMs 是"连上的时刻"，不是心跳。
        # 连接着的节点这个值可以很旧，用它算"掉线"会误报。以 connected 标志为准。
        offline = (connected is False) or (disc > last)
        ref = disc if disc > last else last
        age_min = (now - ref) / 60000 if ref else 99999
        if offline and age_min > STALE_MIN:
            stale.append({'name': name, 'age_min': round(age_min, 1),
                          'offline_flag': offline,
                          'last': time.strftime('%Y-%m-%d %H:%M', time.localtime(last / 1000)) if last else 'never'})
        else:
            fresh.append(name)
    out = {'checked_at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'stale': stale, 'fresh': fresh}
    json.dump(out, open(STATE, 'w'), ensure_ascii=False, indent=1)
    if not stale:
        print('NODE_OK %d 台在期：%s' % (len(fresh), ','.join(fresh)))
        st.pop('last_alert_ts', None)
        json.dump(st, open(STATE + '.dedup', 'w'))
        return 0
    for s in stale:
        print('STALE %s 最后连接 %s（%.0f 分钟前）' % (s['name'], s['last'], s['age_min']))
    # 去重：同一批节点 6 小时内只推一次
    dp = STATE + '.dedup'
    ded = {}
    if os.path.exists(dp):
        try: ded = json.load(open(dp))
        except Exception: ded = {}
    sig = ','.join(sorted(s['name'] for s in stale))
    last_ts = ded.get(sig, 0)
    if time.time() - last_ts > DEDUP_H * 3600:
        msg = '节点掉线：' + '；'.join('%s 最后连接 %s' % (s['name'], s['last']) for s in stale) + '（>%d 分钟）' % STALE_MIN
        subprocess.run(['bash', os.path.join(WS, 'tools', 'notify.sh'), msg], timeout=60)
        ded[sig] = time.time()
        json.dump(ded, open(dp, 'w'))
    # 2026-11-13 修：stale 是「内容结论」不是「脚本故障」。返回 1 会让 systemd 每次把
    # 单元标 failed（节点没上线的整段时间里天天误报 P1）。真实错误仍走异常 → exit 1。
    return 0

if __name__ == '__main__':
    sys.exit(main())
