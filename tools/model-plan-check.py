#!/usr/bin/env python3
"""model-plan-check.py v0.1 — 规划方案的确定性校验/一致性判定（只读）
用法:
  --validate <plan.json>            校验 schema/白名单/容量/改动上限
  --consistency <plan.json> <verdict.json>  判定两模型是否一致
退出码: 0 通过 / 1 违规或不一致 / 2 错误
"""
import json, os, sys

WS = "/home/j/.openclaw/workspace"
POLICY = os.path.join(WS, "state/model-econ/policy.json")
MAX_CHANGES = 3          # 评审共识：单日自动改动上限 3 项（影子期不应用，仅校验）
LIMITED = {"zai/glm-5.3", "ollama/qwen3:30b-a3b-instruct-2507-q4_K_M", "ollama/qwen3:14b"}
HEAVY_KW = ("重活", "批量", "长文", "调试", "全量", "备份")

def load(p):
    with open(p) as f: return json.load(f)

def pool(policy):
    s = set()
    for prov in (policy.get("providers") or {}).values():
        for m in prov.get("models_in_pool") or []:
            s.add(m)
    return s

def validate(plan, policy):
    v = []
    items = plan.get("items")
    if not isinstance(items, list): return ["items 缺失或不是数组"], items or []
    allowed = pool(policy)
    changes = [i for i in items if (i.get("current") or "") != (i.get("suggested") or "")]
    if len(changes) > MAX_CHANGES:
        v.append(f"改动 {len(changes)} 项，超过上限 {MAX_CHANGES}")
    for it in items:
        task = it.get("task") or "?"
        sug = it.get("suggested") or ""
        if sug not in allowed:
            v.append(f"[{task}] 建议模型 {sug} 不在预授权池")
        pri = (it.get("priority") or "").lower()
        heavy = pri == "heavy" or any(k in str(it.get("task","")) for k in HEAVY_KW)
        if heavy and sug in LIMITED:
            v.append(f"[{task}] 重活/时敏被建议切到限流或慢模型 {sug}（容量护栏）")
        if it.get("deadline") and sug in LIMITED:
            v.append(f"[{task}] 有截止时间仍建议限流模型 {sug}")
        if not it.get("reason"):
            v.append(f"[{task}] 缺少理由")
    return v, changes

def consistency(plan, verdict, policy):
    errs, _ = validate(plan, policy)
    out = {"plan_errors": errs}
    if verdict.get("verdict") != "approve":
        out["reason"] = "审查未批准"
        return False, out
    checks = verdict.get("item_checks") or []
    bad = [c for c in checks if not c.get("agree")]
    if bad: out["disagree_items"] = bad
    plan_tasks = {i.get("task") for i in plan.get("items") or []}
    covered = {c.get("task") for c in checks}
    missing = plan_tasks - covered
    if missing: out["uncovered_items"] = sorted(missing)
    ok = (not errs) and (not bad) and (not missing)
    return ok, out

def main():
    a = sys.argv[1:]
    try:
        policy = load(POLICY)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"policy 读取失败: {e}"})); return 2
    try:
        if a and a[0] == "--validate" and len(a) > 1:
            plan = load(a[1]); errs, changes = validate(plan, policy)
            print(json.dumps({"ok": not errs, "errors": errs, "changes": len(changes)}, ensure_ascii=False))
            return 0 if not errs else 1
        if a and a[0] == "--consistency" and len(a) > 2:
            plan = load(a[1]); verdict = load(a[2])
            ok, det = consistency(plan, verdict, policy)
            print(json.dumps({"ok": ok, "detail": det}, ensure_ascii=False))
            return 0 if ok else 1
        print(json.dumps({"ok": False, "error": "用法: --validate plan | --consistency plan verdict"}))
        return 2
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)[:300]}))
        return 2

if __name__ == "__main__":
    sys.exit(main())
