#!/usr/bin/env bash
# channel-check.sh —— 渠道体检清单（2026-09-26 立：接连 5 环，缺一不可）
# 用法: bash channel-check.sh [渠道] [账号名]   例: bash channel-check.sh feishu sheet-music
CH=${1:-feishu}; ACC=${2:-}
echo "🔎 渠道体检 · $CH / ${ACC:-全部} · $(date "+%F %H:%M")"
python3 - "$CH" "$ACC" << "PY"
import json, sys
ch, acc = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
d = json.load(open("/home/j/.openclaw/openclaw.json"))
cfg = (d.get("channels") or {}).get(ch) or {}
accounts = cfg.get("accounts") or {}
names = [acc] if acc else list(accounts.keys())
bindings = d.get("bindings") or []
def find_binding(a):
    for b in bindings:
        m = b.get("match") or {}
        if m.get("channel") == ch and m.get("accountId") == a: return b.get("agentId")
    for b in bindings:
        m = b.get("match") or {}
        if m.get("channel") == ch and m.get("accountId") == "*": return b.get("agentId") + "（兜底 *）"
    return None
for a in names:
    v = accounts.get(a) or {}
    print(f"  ── {a} ──")
    print("   ① 账号配置 :", "✅" if v.get("appId") else "❌ 缺 appId")
    print("   ② 密钥     :", "✅ SecretRef" if isinstance(v.get("appSecret"), dict) else ("⚠️ 明文/缺" if v.get("appSecret") else "❌ 缺 appSecret"))
    print("   ③ 启用     :", "✅" if v.get("enabled", True) else "❌ disabled")
    cm = v.get("connectionMode") or cfg.get("connectionMode") or "(未设置→默认 webhook)"
    print("   ④ 连接方式 :", cm, "← 必须与飞书后台一致" if cm == "(未设置→默认 webhook)" else "")
    print("   ⑤ 路由绑定 :", ("✅ → " + find_binding(a)) if find_binding(a) else "❌ 没有绑定 ← 这就是【配置成功但收不到回复】的原因")
PY
echo "  ── 另需人工确认（飞书后台，脚本看不到）──"
echo "   ⑥ 事件订阅 : 已加 im.message.receive_v1，订阅方式=长连接"
echo "   ⑦ 发布审批 : 应用已创建版本且审批通过（未发布只在开发版生效）"