#!/usr/bin/env python3
"""筛查所有智能体的能力分配：模型 / exec 模式 / deny 列表 / 白名单。
用法: python3 agent-capability-audit.py
输出：逐个管家的能力矩阵 + 异常标记。
"""
import json, subprocess, os

def cfg(path):
    r = subprocess.run(["openclaw","config","get",path,"--json"], capture_output=True, text=True, timeout=60)
    try: return json.loads(r.stdout)
    except Exception: return None

entries = cfg("agents.entries") or {}
approvals = {}
try:
    r = subprocess.run(["openclaw","approvals","get","--json"], capture_output=True, text=True, timeout=60)
    approvals = json.loads(r.stdout or "{}")
except Exception: pass
s = json.dumps(approvals, ensure_ascii=False)

rows = []
for aid, v in entries.items():
    v = v or {}
    t = v.get("tools") or {}
    deny = t.get("deny") or []
    mode = (t.get("exec") or {}).get("mode") or "(默认=full)"
    has_exec = "exec" not in deny
    ocr = "script-mystery" in aid and "ocr-file" in s
    rows.append((aid, v.get("model","-"), has_exec, len(deny), mode, ocr))

rows.sort(key=lambda r: (not r[2], r[0]))
print("【智能体能力筛查】")
print(f"{'管家':<20}{'exec':<6}{'deny':<6}{'exec模式':<12}{'受限OCR'}")
for aid, model, has_exec, nd, mode, ocr in rows:
    flag = "" if (has_exec and mode == "allowlist") or not has_exec else " ⚠️全权"
    print(f"{aid:<20}{'有' if has_exec else '禁':<6}{nd:<6}{mode:<12}{'✅' if ocr else '-':<8}{flag}")

n_full = sum(1 for r in rows if r[2] and r[4] == "(默认=full)")
n_allow = sum(1 for r in rows if r[2] and r[4] == "allowlist")
n_none = sum(1 for r in rows if not r[2])
print(f"\n汇总：无 exec {n_none} 个 · 白名单受限 {n_allow} 个 · ⚠️全权 {n_full} 个")
