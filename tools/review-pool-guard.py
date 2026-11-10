#!/usr/bin/env python3
"""评审池守门人 —— 防止「规则写好了又被绕过/改回去」的机械校验。

检查四件事：
 1. 池自洽：banned 里的模型不得出现在 vendors 里
 2. 文档漂移：USER.md / AGENTS.md / MEMORY.md 的「评审」语境里不得出现禁用模型名
 3. 台账合规：最近 30 条交叉评审记录的模型必须都在池内（2026-11-02 之后的记录）
 4. 真源同步：与模型管家 dispatch-rules.json 的池子比对

用法：python3 tools/review-pool-guard.py [--quiet]
退出码：0 全部通过；1 有违规（逐条打印）
"""
import json
import os
import re
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL = os.path.join(W, "state/model-econ/review-pool.json")
LEDGER = os.path.join(W, "docs/交叉验证台账.md")
TRUTH = "/home/j/.openclaw/workspace-model/state/model-warden/dispatch-rules.json"
DOCS = ["USER.md", "AGENTS.md", "MEMORY.md"]
CUTOFF = "2026-11-02"
problems = []


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def norm(s):
    s = s.lower()
    s = s.split("（")[0].split("(")[0].strip()
    s = s.replace("kimi-k3.1-pro", "kimi-k3").replace("minimax-m3.1", "minimax-m3")
    s = re.sub(r"\s+", "", s)
    return s


def main():
    if not os.path.exists(POOL):
        print("FAIL 池配置文件不存在: " + POOL)
        return 1
    pool = load(POOL)
    vendors = [v["model"] for v in pool.get("vendors", [])]
    banned = [norm(b) for b in pool.get("banned", [])]
    vendor_norm = {norm(v) for v in vendors}
    disp_name = {norm(v).split("/")[-1]: v for v in vendors}

    # 1. 池自洽
    for v in vendors:
        if norm(v) in banned or norm(v).split("/")[-1] in banned:
            problems.append(f"池冲突: {v} 同时在 vendors 和 banned 里")

    # 2. 文档漂移：禁用模型名出现在评审语境附近
    ban_query = [b for b in banned if len(b) > 6]
    for d in DOCS:
        p = os.path.join(W, d)
        if not os.path.exists(p):
            continue
        for i, line in enumerate(open(p, encoding="utf-8", errors="ignore"), 1):
            if not re.search(r"评审|双审|三审|交叉", line):
                continue
            for b in ban_query:
                short = b.split("/")[-1]
                if short in norm(line):
                    # 允许「已移出/作废/排除」这类明确否定的句子
                    if re.search(r"移出|作废|排除|不进池|禁用|停用", line):
                        continue
                    problems.append(f"文档漂移 {d}:{i} 评审条文里出现禁用模型 {b}")
                    break

    # 3. 台账合规
    if os.path.exists(LEDGER):
        rows = [l for l in open(LEDGER, encoding="utf-8", errors="ignore") if l.startswith("|")]
        recent = rows[-30:]
        for r in recent:
            cols = [c.strip() for c in r.strip().strip("|").split("|")]
            if len(cols) < 4:
                continue
            ts, task, models = cols[0], cols[1], cols[2]
            if not re.match(r"\d{4}-\d{2}-\d{2}", ts) or ts[:10] < CUTOFF:
                continue
            for m in re.findall(r"[\w.\-]+/[\w.\-]+|kimi|zhipu|zai|minimax|qianwen|deepseek", models, re.I):
                ml = m.lower()
                if ml in ("kimi", "zhipu", "zai", "minimax", "qianwen", "deepseek"):
                    if ml == "deepseek" and "deepseek" not in {norm(v).split("/")[0] for v in vendors}:
                        problems.append(f"台账违规 {ts} {task}: 用了池外厂商 {m}")
                    continue
                n = norm(ml)
                if n not in vendor_norm and n.split("/")[-1] not in disp_name:
                    problems.append(f"台账违规 {ts} {task}: 模型 {m} 不在池内")

    # 4. 真源同步
    if os.path.exists(TRUTH):
        try:
            t = load(TRUTH)
            blob = json.dumps(t, ensure_ascii=False)
            missing = [v for v in vendors if v.split("/")[-1] not in blob]
            if missing:
                problems.append("真源不一致: dispatch-rules.json 里找不到 " + ", ".join(missing))
        except Exception as e:
            problems.append(f"真源读取失败: {e}")
    else:
        print("WARN 真源文件不可达（跳过第4项）: " + TRUTH)

    if problems:
        print("评审池体检 FAIL —— %d 项：" % len(problems))
        for p in problems:
            print("  ✗ " + p)
        return 1
    if "--quiet" not in sys.argv:
        print(f"评审池体检 PASS —— 池内 {len(vendors)} 家（{'/'.join(m.split('/')[-1] for m in vendors)}），禁用 {len(pool.get('banned', []))} 项，台账近 30 条无违规")
    return 0


if __name__ == "__main__":
    sys.exit(main())
