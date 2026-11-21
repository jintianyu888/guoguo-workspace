#!/usr/bin/env python3
"""gateway-lease-heal.py —— 清掉陈旧的网关所有权租约，解决 GatewayLockNamespaceError 起不来

背景：2026-11-21 两次事故。WSL 发行版重启后 PID namespace 变化，state_leases 里
scope='gateway-owner' 的旧记录无法验证归属（namespace=unknown），网关拒绝启动，
本次卡了 50 分钟、当天累计 93 分钟。

安全边界（宁可不修，不可误删）：
1. 只在网关未运行时动手（ExecStartPre 场景）；active/activating 一律退出。
2. 记录里的 owner pid 若仍活着且确实是 openclaw 进程 → 不动。
3. 只删 scope='gateway-owner' 这一行，不碰其他租约、不写别的表。
4. 每次动作写 state/work/gateway-lease-heal.log，带前后快照。
"""
import json, os, sqlite3, subprocess, sys
from datetime import datetime, timezone, timedelta

W = '/home/j/.openclaw/workspace'
DB = os.environ.get('OC_LEASE_DB', '/home/j/.openclaw/state/openclaw.sqlite')
LOG = os.path.join(W, 'state/work/gateway-lease-heal.log')
CST = timezone(timedelta(hours=8))


def log(msg):
    line = '[%s] %s' % (datetime.now(CST).strftime('%F %T'), msg)
    print(line)
    try:
        open(LOG, 'a').write(line + chr(10))
    except Exception:
        pass


def unit_active():
    if os.environ.get('OC_LEASE_TEST'):   # 仅测试用：--test 模拟网关已停
        return False
    try:
        r = subprocess.run(['systemctl', '--user', 'is-active', 'openclaw-gateway'],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() in ('active', 'activating', 'reloading', 'deactivating')
    except Exception:
        return True   # 判不准就当活着，宁可不修


def pid_alive_openclaw(pid):
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    try:
        cmd = open('/proc/%d/cmdline' % pid, 'rb').read().decode('utf-8', 'ignore')
    except FileNotFoundError:
        return False
    except Exception:
        return True
    return 'openclaw' in cmd


def main():
    if unit_active():
        log('网关仍在运行，跳过')
        return 0
    if not os.path.exists(DB):
        log('state 库不存在，跳过')
        return 0
    try:
        c = sqlite3.connect('file:%s?mode=rw' % DB, uri=True, timeout=15)
        c.execute('PRAGMA busy_timeout=15000')
        row = c.execute("select owner,payload_json,expires_at from state_leases "
                        "where scope='gateway-owner' and lease_key='global'").fetchone()
        if not row:
            log('无网关租约，无需处理')
            return 0
        owner, payload, expires = row
        try:
            pid = json.loads(payload or '{}').get('owner', {}).get('pid')
        except Exception:
            pid = None
        if pid and pid_alive_openclaw(pid):
            log('租约持有者 pid=%s 仍存活，保持不变' % pid)
            return 0
        c.execute("delete from state_leases where scope='gateway-owner' and lease_key='global'")
        c.commit()
        log('已清除陈旧网关租约 owner=%s pid=%s expires=%s' % (owner, pid, expires))
        return 0
    except sqlite3.OperationalError as e:
        log('库被占用，跳过（%s）' % e)
        return 0
    except Exception as e:
        log('异常，跳过（%s）' % e)
        return 0


if __name__ == '__main__':
    sys.exit(main())
