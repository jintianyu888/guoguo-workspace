#!/usr/bin/env python3
"""model-compliance-check.py v1.0 (2026-11-18) —— 模型分配合规检查（零 token，可作 kill 判据）
检查三项：
 1 千问铁律：有 cron 任务的管家不得使用 qianwen（禁止自动化/cron）
 2 kimi 清零：本周期 kimi 全模型 FAIL，不得出现在主模型或 fallback
 3 单厂集中度：任一 provider 占主模型 >45% 判 FAIL
退出码：0 全过，1 有违规（可接 cron/systemd 做门禁）
"""
import collections, json, subprocess, sys

CFG = "/home/j/.openclaw/openclaw.json"
LIMIT = 0.45

def cron_counts():
    try:
        r = subprocess.run(["openclaw", "cron", "list", "--json"], capture_output=True, text=True, timeout=120)
        jobs = json.loads(r.stdout).get("jobs", [])
        return collections.Counter(j.get("agentId") for j in jobs if j.get("enabled", True))
    except Exception:
        return collections.Counter()

def main():
    cfg = json.load(open(CFG, encoding="utf-8"))
    e = cfg["agents"]["entries"]
    cnt = cron_counts()
    fail = []
    q_viol, kimi_refs = [], []
    prim = collections.Counter()
    for aid, v in e.items():
        m = v.get("model") or {}
        s = json.dumps(m, ensure_ascii=False)
        p = (m.get("primary") or "").split("/")[0] or "default"
        prim[p] += 1
        if "qianwen" in s and cnt.get(aid, 0) > 0:
            q_viol.append("%s(cron=%d)" % (aid, cnt.get(aid, 0)))
        if "kimi" in s:
            kimi_refs.append(aid)
    print("① 千问铁律违规：", "无" if not q_viol else "、".join(q_viol))
    print("② kimi 残留引用：", 0 if not kimi_refs else "、".join(kimi_refs))
    total = sum(prim.values()) or 1
    top = prim.most_common(1)[0] if prim else ("-", 0)
    share = top[1] / total
    print("③ 单厂集中度：%s %d/%d = %.0f%%（上限 45%%）" % (top[0], top[1], total, share * 100))
    if q_viol: fail.append("千问铁律")
    if kimi_refs: fail.append("kimi 残留")
    if share > LIMIT: fail.append("集中度")
    print("结论：", "PASS" if not fail else "FAIL（%s）" % "、".join(fail))
    sys.exit(0 if not fail else 1)

if __name__ == "__main__":
    main()

