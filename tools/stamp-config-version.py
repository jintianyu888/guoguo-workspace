#!/usr/bin/env python3
"""stamp-config-version.py <version> —— 把 openclaw.json 的 meta.lastTouchedVersion 改成指定版本

用途：降级/回滚时，新版写下的版本戳会让旧版二进制拒绝启动
（Refusing to start ... older than the config last written by OpenClaw X）。
改戳前自动留 .bak-<ts>，只动这一个字段，其余配置原样。
2026-11-26 事故教训（回滚 11.10→11.9 被降级保护挡住，网关中断 40 分钟）。
"""
import json, os, shutil, sys, time

if len(sys.argv) != 2:
    print("用法: stamp-config-version.py <版本>"); sys.exit(2)
ver = sys.argv[1].strip()
p = "/home/j/.openclaw/openclaw.json"
c = json.load(open(p, encoding="utf-8"))
meta = c.setdefault("meta", {})
old = meta.get("lastTouchedVersion")
if old == ver:
    print("已是 %s，无需改" % ver); sys.exit(0)
bak = p + ".bak-stamp-" + time.strftime("%Y%m%d-%H%M%S")
shutil.copy2(p, bak)
meta["lastTouchedVersion"] = ver
json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("版本戳 %s → %s（备份 %s）" % (old, ver, bak))
