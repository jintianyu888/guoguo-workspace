#!/usr/bin/env python3
"""model-migrate-1201.py v1.0 (2026-11-18) —— 千问套餐到期前迁移（12-01）
千问 Token Plan 12-01 到期且条款禁止 cron/批量，所以到期前把仍在千问的管家
按「轮转」分到 zai / minimax / deepseek 三家，避免到期当天齐哑、也避免单厂超 45%。

用法:
  python3 tools/model-migrate-1201.py --dry-run      # 只出计划，不写配置
  python3 tools/model-migrate-1201.py --apply        # 落盘（先备份，再 patch，再校验）
"""
import argparse, json, os, shutil, subprocess, sys, datetime

WS = "/home/j/.openclaw/workspace"
CFG = "/home/j/.openclaw/openclaw.json"
TARGETS = ["zai/glm-5.3-flash", "minimax/MiniMax-M3.1-Flash-Preview"]  # 2026-11-18: 去掉 deepseek（真实调用占比 86%，再迁入会加深单点）
FB = {
 "zai/glm-5.3-flash": ["minimax/MiniMax-M3.1-Flash-Preview", "deepseek/deepseek-flash"],
 "minimax/MiniMax-M3.1-Flash-Preview": ["zai/glm-5.3-flash", "deepseek/deepseek-flash"],
 "deepseek/deepseek-flash": ["zai/glm-5.3-flash", "minimax/MiniMax-M3.1-Flash-Preview"],
}

def build_plan():
    cfg = json.load(open(CFG, encoding="utf-8"))
    e = cfg["agents"]["entries"]
    users = sorted(a for a, v in e.items() if "qianwen" in json.dumps(v.get("model") or {}))
    patch = {"agents": {"entries": {}}}
    plan = []
    for i, a in enumerate(users):
        tgt = TARGETS[i % len(TARGETS)]
        patch["agents"]["entries"][a] = {"model": {"primary": tgt, "fallbacks": list(FB[tgt])}}
        plan.append((a, tgt))
    return users, patch, plan

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if not (a.dry_run or a.apply):
        ap.error("请指定 --dry-run 或 --apply")
    users, patch, plan = build_plan()
    if not users:
        print("没有管家在使用千问，无需迁移")
        return
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    print("待迁移 %d 个：" % len(users))
    for a_, t in plan:
        print("  %-18s -> %s" % (a_, t))
    if a.dry_run:
        print("dry-run：计划已生成，未写入配置")
        return
    bk = os.path.join(WS, "state/backup/config/model-migrate-1201-%s.json" % ts)
    os.makedirs(os.path.dirname(bk), exist_ok=True)
    shutil.copy2(CFG, bk)
    pf = "/tmp/model-migrate-%s.json" % ts
    json.dump(patch, open(pf, "w"), ensure_ascii=False, indent=1)
    r = subprocess.run(["openclaw", "config", "patch", "--file", pf], capture_output=True, text=True, timeout=180)
    out = (r.stdout or "") + (r.stderr or "")
    ok = "Applied" in out or r.returncode == 0
    print("patch rc=%s ok=%s 备份=%s" % (r.returncode, ok, bk))
    if not ok:
        print(out[-500:]); sys.exit(2)
    subprocess.run(["python3", os.path.join(WS, "tools/model-ledger.py"), "sync-config"], timeout=120)
    left = subprocess.run(["python3", "-c",
        "import json;e=json.load(open('%s'))['agents']['entries'];"
        "print(sum(1 for v in e.values() if 'qianwen' in json.dumps(v.get('model') or {})))" % CFG],
        capture_output=True, text=True)
    print("迁移后仍在千问的管家数：", (left.stdout or "").strip())
    subprocess.run(["bash", os.path.join(WS, "tools/notify.sh"),
                    "【千问到期迁移】已执行：%d 个管家迁出千问\n备份：%s" % (len(users), bk)], timeout=60)

if __name__ == "__main__":
    main()

