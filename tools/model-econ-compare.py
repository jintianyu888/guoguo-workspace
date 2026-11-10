#!/usr/bin/env python3
"""model-econ-compare.py v0.1 — 各模型/套餐实际价差分析（只读）
数据源：usage_by_model.py 报表 + ds-burn.csv 实付账本 + policy.json 套餐价
产出：state/model-econ/compare-YYYYMMDD.{json,md}
"""
import json, os, subprocess, sys, csv
from datetime import datetime

WS="/home/j/.openclaw/workspace"; D=WS+"/state/model-econ"
DAYS=int(sys.argv[sys.argv.index("--days")+1]) if "--days" in sys.argv else 7

def sh(cmd, t=180):
    p=subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=t)
    return p.stdout

def main():
    usage=json.loads(sh(f"cd {WS} && python3 tools/usage_by_model.py --days {DAYS} --json") or "{}")
    models=usage.get("models",{})
    pol={}
    try: pol=json.load(open(D+"/policy.json"))
    except Exception: pass
    # 实际账本（DeepSeek 现付）
    tin=tout=tcost=0.0
    try:
        with open(WS+"/state/ds-burn.csv") as f:
            r=csv.reader(f); next(r,None)
            for row in r:
                if len(row)>=6:
                    try:
                        i=int(float(row[3] or 0)); o=int(float(row[4] or 0)); c=float(row[5] or 0)
                        tin+=i; tout+=o; tcost+=c
                    except: pass
    except Exception: pass
    ds_actual = tcost/((tin+tout)/1e6) if (tin+tout) else None
    rows=[]
    for k,v in models.items():
        i=v.get("input",0); cr=v.get("cacheRead",0); o=v.get("output",0); c=v.get("totalCost",0)
        tot=i+cr+o
        rows.append({"model":k,"calls":v.get("calls",0),"in":i,"cache":cr,"out":o,"tokens":tot,
                     "runtime_cost":round(c,4),
                     "yuan_per_M": round(c/(tot/1e6),4) if tot else None})
    rows.sort(key=lambda x:-(x["tokens"]))
    glm=next((r for r in rows if "glm" in r["model"]),None)
    plans=[]
    fee=94.4; wk=fee*12/52
    if glm and glm["tokens"]:
        tok_per_credit = glm["tokens"]/3227
        full= tok_per_credit*10000
        plans.append({"plan":"GLM Coding 季卡","fee_month":fee,"fee_week":round(wk,2),
                      "measured_tokens":glm["tokens"],"measured_credits":3227,
                      "tokens_per_credit":round(tok_per_credit),
                      "full_quota_tokens":round(full),
                      "cost_per_M_at_current": round(wk/(glm["tokens"]/1e6),2),
                      "cost_per_M_at_full": round(wk/(full/1e6),2),
                      "breakeven_utilization": round(wk/( (full/1e6)*2.0919 )*100,1)})
    out={"generated":datetime.now().isoformat(timespec="seconds"),"days":DAYS,
         "deepseek_actual_yuan_per_M": round(ds_actual,4) if ds_actual else None,
         "deepseek_billed_tokens":{"in":int(tin),"out":int(tout),"cost":round(tcost,2)},
         "models":rows,"plans":plans}
    os.makedirs(D,exist_ok=True)
    day=datetime.now().strftime("%Y%m%d")
    json.dump(out,open(f"{D}/compare-{day}.json","w"),ensure_ascii=False,indent=1)
    lines=[f"# 模型价差分析 {day}（近{DAYS}天）","",
           f"DeepSeek 实付：¥{tcost:.2f} / {int(tin+tout):,} tokens → **¥{ds_actual:.4f}/百万** (缓存另计)","",
           "| 模型 | 调用 | 入 | 缓存读 | 出 | 运行时成本 | ¥/百万(全量) |","|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['model']} | {r['calls']} | {r['in']:,} | {r['cache']:,} | {r['out']:,} | {r['runtime_cost']} | {r['yuan_per_M']} |")
    if plans:
        lines+=["","## 套餐视角",""]
        for p in plans:
            lines.append(f"- {p['plan']}: 月费¥{p['fee_month']}（周¥{p['fee_week']}）｜实测 {p['measured_tokens']:,} tokens / {p['measured_credits']} credits")
            lines.append(f"  - 1 credit ≈ {p['tokens_per_credit']} tokens；用满额度 ≈ {p['full_quota_tokens']:,} tokens/周")
            lines.append(f"  - 当前用量摊薄：¥{p['cost_per_M_at_current']}/百万；用满摊薄：¥{p['cost_per_M_at_full']}/百万")
            lines.append(f"  - 盈亏平衡用满率 ≈ {p['breakeven_utilization']}%")
    open(f"{D}/compare-{day}.md","w").write("\n".join(lines)+"\n")
    print("\n".join(lines[:40]))
    print("\n报告:",f"{D}/compare-{day}.md")

if __name__=="__main__":
    main()
