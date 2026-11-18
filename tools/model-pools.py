#!/usr/bin/env python3
"""model-pools.py v1.0 (2026-11-18) —— 模型「池化」生成器
思路：人工只维护 state/model-econ/pools.json（几个池 + agent 归属），
openclaw.json 里的 model 字段由本工具生成。这样换模型 = 改池 + apply，
不用再手改 38 处；集中度 = 池的权重，可机器核算。

用法:
  python3 tools/model-pools.py --seed     # 从当前配置生成 pools.json（首次）
  python3 tools/model-pools.py --diff     # 显示「池 vs 现状」差异，不改配置
  python3 tools/model-pools.py --apply    # 按池生成配置（先备份）
  python3 tools/model-pools.py --share    # 按池统计主模型占比（验收口径）
"""
import json, os, shutil, subprocess, sys, datetime, collections

WS = "/home/j/.openclaw/workspace"
CFG = "/home/j/.openclaw/openclaw.json"
POOLS = os.path.join(WS, "state/model-econ/pools.json")

def load(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d if d is not None else {}

def seed():
    cfg = load(CFG); e = cfg["agents"]["entries"]
    groups = collections.defaultdict(list)
    for a, v in e.items():
        m = v.get("model") or {}
        prim = m.get("primary") or "(default)"
        groups[prim].append(a)
    pools, members = {}, {}
    for prim, agents in groups.items():
        pid = "pool-" + prim.split("/")[-1].replace(":", "-")
        m0 = (e[agents[0]].get("model") or {})
        pools[pid] = {"primary": prim, "fallbacks": m0.get("fallbacks") or [],
                      "why": "seed: 沿用现状，待人工归类"}
        for a in agents: members[a] = pid
    out = {"schema": "model-pools/v1", "updated_at": datetime.datetime.now().strftime("%F %T"),
           "note": "人工只改本文件；openclaw.json 的 model 字段由 tools/model-pools.py --apply 生成",
           "pools": pools, "agents": members}
    os.makedirs(os.path.dirname(POOLS), exist_ok=True)
    json.dump(out, open(POOLS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("已生成 %s：%d 个池 / %d 个 agent" % (POOLS, len(pools), len(members)))

def build_patch():
    P = load(POOLS)
    if not P.get("pools"): sys.exit("先跑 --seed 生成 pools.json")
    cfg = load(CFG); e = cfg["agents"]["entries"]
    patch = {"agents": {"entries": {}}}; diffs = []
    rot_cache = {}
    for a, pid in sorted(P["agents"].items()):
        pool = P["pools"].get(pid)
        if not pool: diffs.append((a, pid, "池不存在")); continue
        rot = pool.get("rotation")
        if rot:
            if pid not in rot_cache:
                # 按池内成员稳定排序后轮转，保证同名 agent 每次落到同一 provider
                members = sorted(x for x, q in P["agents"].items() if q == pid)
                rot_cache[pid] = {m: rot[i % len(rot)] for i, m in enumerate(members)}
            prim = rot_cache[pid][a]
            want = {"primary": prim, "fallbacks": [x for x in (pool.get("fallbacks") or []) if x != prim][:3]}
        else:
            want = {"primary": pool["primary"], "fallbacks": pool.get("fallbacks") or []}
        cur = (e.get(a, {}) or {}).get("model") or {}
        if cur.get("primary") != want["primary"] or (cur.get("fallbacks") or []) != want["fallbacks"]:
            diffs.append((a, pid, "%s -> %s" % (cur.get("primary"), want["primary"])))
            patch["agents"]["entries"][a] = {"model": want}
    return patch, diffs

def main():
    a = sys.argv[1:]
    if "--seed" in a: seed(); return
    if "--share" in a:
        P = load(POOLS); cnt = collections.Counter(p["primary"].split("/")[0] for p in P["pools"].values()
                                                   for _ in range(0))  # placeholder
        w = collections.Counter()
        for agent, pid in sorted(P["agents"].items()):
            pool = P["pools"].get(pid)
            if not pool: continue
            rot = pool.get("rotation")
            if rot:
                members = sorted(x for x, q in P["agents"].items() if q == pid)
                idx = members.index(agent) % len(rot)
                w[rot[idx].split("/")[0]] += 1
            else:
                w[pool["primary"].split("/")[0]] += 1
        total = sum(w.values()) or 1
        for k, v in w.most_common():
            print("%-12s %2d/%d = %.0f%%" % (k, v, total, 100 * v / total))
        return
    patch, diffs = build_patch()
    if "--diff" in a:
        print("差异 %d 条" % len(diffs))
        for d in diffs[:40]: print("  %-18s %-28s %s" % d)
        return
    if "--apply" in a:
        if not patch["agents"]["entries"]:
            print("无需变更（池与现状一致）"); return
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        bk = os.path.join(WS, "state/backup/config/pools-%s.json" % ts)
        os.makedirs(os.path.dirname(bk), exist_ok=True); shutil.copy2(CFG, bk)
        pf = "/tmp/pools-patch-%s.json" % ts
        json.dump(patch, open(pf, "w"), ensure_ascii=False, indent=1)
        r = subprocess.run(["openclaw", "config", "patch", "--file", pf], capture_output=True, text=True, timeout=240)
        ok = r.returncode == 0
        print("apply rc=%s 变更=%d 备份=%s" % (r.returncode, len(patch["agents"]["entries"]), bk))
        if not ok: print(((r.stdout or "") + (r.stderr or ""))[-400:])
        return
    print(__doc__)

if __name__ == "__main__":
    main()

