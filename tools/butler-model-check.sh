#!/bin/bash
# butler-model-check.sh v1.0 (2026-11-18) —— 给管家用的只读模型体检（固定参数，无入参）
# 由果果维护；结果只读，不含写操作。
W=/home/j/.openclaw/workspace
echo "=== 一、分配合规（千问铁律/kimi/集中度）"
python3 "$W/tools/model-compliance-check.py" 2>&1
echo
echo "=== 二、智谱额度"
python3 "$W/tools/glm-quota-guard.py" 2>&1
echo
echo "=== 三、模型健康（30 分钟窗）"
python3 - <<'PY' 2>&1
import json
p="/home/j/.openclaw/workspace/state/model-health/status.json"
try:
    d=json.load(open(p))
    for k,v in (d.get("models") or {}).items():
        print("  %-45s %-8s ok=%s fails=%s" % (k, v.get("status"), v.get("ok_window"), v.get("fails_window")))
except Exception as e:
    print("  读取失败:", e)
PY

