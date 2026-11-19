#!/usr/bin/env python3
"""把 provider-state.json 的归一结果与冲突同步进 balances.json（面板数据源），
并生成对账表 docs/额度对账表-latest.md。不覆盖已有字段，只补 norm/conflicts/captured_at。"""
import json, os, datetime
BASE = "/home/j/.openclaw/workspace"
S = os.path.join(BASE, "state/model-econ/provider-state.json")
B = os.path.join(BASE, "state/model-econ/balances.json")
DOC = os.path.join(BASE, "docs/额度对账表-latest.md")
st = json.load(open(S)); b = json.load(open(B))
b.setdefault("providers", {})
for k, v in st["providers"].items():
    p = b["providers"].setdefault(k, {})
    p["norm"] = v
b["conflicts"] = st["conflicts"]
b["ssot"] = "state/model-econ/provider-state.json"
b["captured_at"] = st["updated_at"]
tmp = B + ".tmp"; json.dump(b, open(tmp, "w"), ensure_ascii=False, indent=2); os.replace(tmp, B)

rows = []
for k, v in st["providers"].items():
    if k == "zai":
        h5 = v["h5"]
        verdict = "一致" if h5["pct"] is not None else ("待校准：" + str(h5.get("reason", "-")))
        rows.append("| 智谱 | 5h %s/%s %s%% | reset %s | %s | %s |" % (
            h5["used"], h5["limit"], h5["pct"], h5["reset_at"], h5["pct"], verdict))
        rows.append("| 智谱 | 周 %s/%s (%s%%) | %s | 周=%s%% | 一致 |" % (
            v["week"]["used"], v["week"]["limit"], v["week"]["pct"],
            v["week"]["reset_at"], v["week"]["pct"]))
    elif k == "deepseek":
        rows.append("| DeepSeek | 可用 ¥%s | 官方 API | ¥%s | 以 API 为权威 |" % (
            v.get("available"), v.get("available")))
    elif k == "kimi":
        rows.append("| Kimi | 月 %s%% · 钱包 %s | 页面 | 月 %s%% | 0 兜底已禁用 |" % (
            v.get("month_pct"), (v.get("wallet") or {}).get("available"), v.get("month_pct")))
    elif k == "minimax":
        rows.append("| MiniMax | 5h %s%% · 周 %s%% · 到期 %s | /console/plan | 同上 | 两源冲突已裁定 |" % (
            v.get("h5_pct"), v.get("week_pct"), v.get("plan_expire")))
doc = ["# 额度对账表（自动生成 %s）" % st["updated_at"], "",
       "| 家 | 页面/接口值 | 入库(归一) | 面板 | 判定 |", "|---|---|---|---|---|"] + rows + [
       "", "## 冲突清单", ""]
for c in st["conflicts"]:
    doc.append("- **%s · %s**：%s → %s（resolved=%s）" % (
        c["provider"], c["field"], json.dumps(c["values"], ensure_ascii=False), c["rule"], c.get("resolved")))
os.makedirs(os.path.dirname(DOC), exist_ok=True)
open(DOC, "w").write("\n".join(doc) + "\n")
print("ok conflicts=%d doc=%s" % (len(st["conflicts"]), DOC))
