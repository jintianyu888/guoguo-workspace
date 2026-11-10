#!/usr/bin/env python3
# pkg-audit.py — A 机软件盘查（只读）：找出「装了但没人用」的包
# 输出：/tmp/pkg-audit-report.txt，并在 stdout 给摘要
import os, re, subprocess, json, sys

STATUS = '/var/lib/dpkg/status'

def parse_status():
    pkgs = {}
    cur = {}
    with open(STATUS, errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line.strip():
                if cur.get('Package'):
                    pkgs[cur['Package']] = cur
                cur = {}
                continue
            if line.startswith(' ') or ':' not in line:
                continue
            k, v = line.split(':', 1)
            cur[k.strip()] = v.strip()
    if cur.get('Package'):
        pkgs[cur['Package']] = cur
    return pkgs

def run(c):
    try:
        return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return ''

KEEP = set('''
systemd systemd-sysv systemd-timesyncd udev dbus dbus-user-session dbus-bin
sudo passwd login adduser ca-certificates openssh-server openssh-client
apt dpkg apt-utils debconf bash coreutils util-linux procps sed grep gawk mawk findutils tar gzip xz-utils
libc6 libstdc++6 gcc-13-base base-files base-passwd dpkg-dev
python3 python3-minimal python3-pip python3-venv python3-dev python3-setuptools python3-wheel
nodejs npm git git-lfs curl wget gnupg gpgv
ffmpeg sqlite3 rsync unzip zip htop lsof psmisc net-tools iproute2 iputils-ping
tzdata locales vim-common nano less man-db
libasound2t64 libgl1 libglib2.0-0 libgomp1 libgstreamer1.0-0
wslu wsl-setup
cifs-utils poppler-utils imagemagick img2pdf ubuntu-minimal ubuntu-wsl apt-transport-https

kernel-wedge linux-base
'''.split())

PROTECT = re.compile(r'^(lib|linux-|initramfs|grub|shim|fonts-|x11|xserver|mesa|gir1.2|gstreamer|python3-[a-z0-9.]+$|perl|ruby|php)', re.I)

def main():
    pkgs = parse_status()
    installed = {n: p for n, p in pkgs.items() if p.get('Status', '').endswith('installed')}
    manual = set(run('apt-mark showmanual').split())

    # 反向依赖
    rev = {}
    for n, p in installed.items():
        for field in ('Depends', 'Pre-Depends', 'Recommends'):
            for part in (p.get(field) or '').split(','):
                name = part.strip().split(' ')[0].split(':')[0]
                name = re.sub(r'[()|].*', '', name).strip()
                if name:
                    rev.setdefault(name, set()).add(n)

    # 被 systemd 单元 / crontab 引用的
    refs = set()
    unit_txt = run("grep -rhoE '^(ExecStart|ExecStop|Environment)=.*' /etc/systemd/system /lib/systemd/system /home/j/.config/systemd/user 2>/dev/null")
    cron_txt = run('crontab -l 2>/dev/null; cat /etc/crontab 2>/dev/null')
    usage_blob = (unit_txt + '\n' + cron_txt).lower()

    def size_mb(p):
        try:
            return int(p.get('Installed-Size', 0)) / 1024.0
        except Exception:
            return 0.0

    cands, soft, keep = [], [], []
    for n in sorted(manual):
        p = installed.get(n)
        if not p:
            continue
        mb = size_mb(p)
        section = p.get('Section', '?')
        prio = p.get('Priority', '')
        deps_on_it = sorted(x for x in rev.get(n, set()) if x != n)
        external_deps = [d for d in deps_on_it if d not in manual]
        rec = {'name': n, 'mb': round(mb, 1), 'section': section, 'priority': prio,
               'rev': deps_on_it[:6], 'rev_n': len(deps_on_it)}
        if n in KEEP or prio in ('required', 'important', 'standard') or p.get('Essential') == 'yes':
            keep.append(rec)
        elif external_deps:
            soft.append(rec)
        elif PROTECT.match(n):
            soft.append(rec)
        elif n.lower() in usage_blob:
            soft.append(rec)
        else:
            cands.append(rec)

    cands.sort(key=lambda r: -r['mb'])
    out = []
    out.append('A 机（WSL Ubuntu）软件盘查 · ' + run('date "+%Y-%m-%d %H:%M"').strip())
    out.append('已装包 %d，手动标记 %d，其中判定可删 %d 个（合计 %.1f MB）' % (
        len(installed), len(manual), len(cands), sum(r['mb'] for r in cands)))
    out.append('')
    out.append('== A. 建议卸载（手动装的、没有别的包依赖它、不在保护名单） ==')
    for r in cands:
        out.append('  %-32s %8.1f MB  %-18s 被依赖0' % (r['name'], r['mb'], r['section']))
    out.append('')
    out.append('== B. 需确认（有包依赖它 / 名字像库 / 被服务引用） ==')
    for r in soft:
        out.append('  %-32s %8.1f MB  %-18s 被%d个包依赖' % (r['name'], r['mb'], r['section'], r['rev_n']))
    out.append('')
    out.append('== C. 保留（基础系统 / 明确还在用） ==')
    for r in keep:
        out.append('  %-32s %8.1f MB' % (r['name'], r['mb']))
    out.append('')
    out.append('== D. 其它包管理器 ==')
    out.append('snap: ' + (run('snap list 2>/dev/null') or '(无)').replace(chr(10), ' | '))
    out.append('flatpak: ' + (run('flatpak list --app --columns=application,size 2>/dev/null') or '(未安装或无应用)').replace(chr(10), ' | '))
    out.append('npm -g: ' + (run('npm ls -g --depth=0 --parseable 2>/dev/null | tail -n +2') or '(无)').replace(chr(10), ' | '))
    txt = chr(10).join(out)
    open('/tmp/pkg-audit-report.txt', 'w').write(txt + chr(10))
    print(txt)

if __name__ == '__main__':
    main()
