#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验收：指定配对节点的 OpenClaw 版本与在线状态。
用法: python3 tools/verify-node-version.py <节点名> <期望版本>
rc=0 达标；rc=1 不达标；rc=2 取不到节点列表。
"""
import json, subprocess, sys

def main():
    if len(sys.argv) != 3:
        print(__doc__ or "用法: verify-node-version.py <节点名> <期望版本>")
        return 2
    name, want = sys.argv[1], sys.argv[2]
    try:
        out = subprocess.run(["openclaw", "nodes", "status", "--json"],
                             capture_output=True, text=True, timeout=60).stdout
        data = json.loads(out)
    except Exception as e:
        print("取节点列表失败:", e)
        return 2
    hit = [n for n in data.get("nodes", []) if n.get("displayName") == name]
    if not hit:
        print(f"未找到节点 {name}")
        return 1
    n = hit[0]
    ver, conn = n.get("version"), bool(n.get("connected"))
    print(f"{name} version={ver} connected={conn} (期望 {want})")
    return 0 if (ver == want and conn) else 1

if __name__ == "__main__":
    sys.exit(main())
