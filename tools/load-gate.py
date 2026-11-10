#!/usr/bin/env python3
"""负载闸门：等 CPU 利用率降到目标以下再跑命令，避免打满。
用法: load-gate.py [--target 50] [--max-wait 3600] -- <命令...>
退出码: 0=已执行（命令的退出码）  2=等待超时未执行
"""
import argparse, os, subprocess, sys, time

def cpu_util(sample=0.5):
    def snap():
        with open('/proc/stat') as f: v=[int(x) for x in f.readline().split()[1:]]
        return v[3]+v[4], sum(v)
    i0,t0=snap(); time.sleep(sample); i1,t1=snap()
    return 100*(1-(i1-i0)/max(1,(t1-t0)))

p=argparse.ArgumentParser()
p.add_argument("--target", type=float, default=50.0, help="目标利用率上限(%%)")
p.add_argument("--max-wait", type=int, default=3600)
p.add_argument("cmd", nargs=argparse.REMAINDER)
a=p.parse_args()
cmd=[c for c in a.cmd if c!="--"]
if not cmd:
    print("用法: load-gate.py [--target 50] -- <命令...>"); sys.exit(1)

t0=time.time(); waited=False
while True:
    u=cpu_util()
    if u <= a.target: break
    if time.time()-t0 > a.max_wait:
        print(f"⏱ 等待超时（当前 {u:.0f}% > 目标 {a.target:.0f}%）", file=sys.stderr); sys.exit(2)
    if not waited:
        print(f"⏳ 当前 CPU {u:.0f}% > 目标 {a.target:.0f}%，等待中…", file=sys.stderr); waited=True
    time.sleep(5)

os.execvp(cmd[0], cmd)
