#!/bin/sh
# ds-balance.sh —— 输出 DeepSeek 实时余额（人民币/美元，含是否可用）
# 2026-10-07：改为【自动跟随网关当前生效的 DeepSeek key】——按 provider apiKey 指向的
#   auth profile / secret store 引用动态解析，不再依赖固定的可读副本（旧副本会随密钥轮换失效）。
#   解析顺序：provider 当前 key(deepseek:manual) → openclaw status --usage；2026-10-30 摘除欠费美元 key fallback（双审修正）。
# 仅用于查询余额；密钥不回显、不外传。

# 优先读模型经济中枢的实时快照（密钥已 write-only，无法直连 API）
S=$(python3 /home/j/.openclaw/workspace/tools/ds-balance-snapshot.py 2>/dev/null)
if [ -n "$S" ]; then echo "$S"; exit 0; fi

KEY=$(python3 - <<'PY'
import json, sqlite3, os, sys
cfg_path  = os.path.expanduser('~/.openclaw/openclaw.json')
gw_db     = os.path.expanduser('~/.openclaw/state/openclaw.sqlite')
agent_db  = os.path.expanduser('~/.openclaw/agents/main/agent/openclaw-agent.sqlite')
key = ''

def secret_value(name):
    try:
        c = sqlite3.connect('file:%s?mode=ro' % gw_db, uri=True)
        row = c.execute(
            "select value from secret_store_entries where name=? and deleted_at_ms is null",
            (name,)).fetchone()
        return (row[0] or '') if row else ''
    except Exception:
        return ''

try:
    cfg = json.load(open(cfg_path))
    ak = cfg.get('models', {}).get('providers', {}).get('deepseek', {}).get('apiKey')
    if isinstance(ak, str):
        if ak.startswith('sk-'):
            key = ak
        elif ak.startswith('${secret:'):
            key = secret_value(ak[len('${secret:'):-1])
    if not key:
        # 2026-10-31 增补：provider apiKey 已被 UI 清掉时，按 main agent 的
        # auth profile 顺序取 deepseek 首个 profile 的 keyRef 解引用
        c = sqlite3.connect('file:%s?mode=ro' % agent_db, uri=True)
        row = c.execute(
            "select store_json from auth_profile_store where store_key='primary'").fetchone()
        row2 = c.execute(
            "select state_json from auth_profile_state where state_key='primary'").fetchone()
        order = []
        profiles = {}
        if row:
            profiles = json.loads(row[0]).get('profiles', {})
        if row2:
            order = json.loads(row2[0]).get('order', {}).get('deepseek', [])
        for pid in order or list(profiles.keys()):
            ent = profiles.get(pid) or {}
            if ent.get('provider') != 'deepseek':
                continue
            k = ent.get('key')
            if isinstance(k, str) and k.startswith('sk-'):
                key = k
                break
            ref = ent.get('keyRef') or {}
            if ref.get('id'):
                key = secret_value(ref['id'])
                if key:
                    break
except Exception:
    pass
print(key or '')
PY
)
case "$KEY" in
  STORE:*) KEY=$(timeout 10 openclaw secrets store get "${KEY#STORE:}" --plain 2>/dev/null) ;;
esac

if [ -n "$KEY" ]; then
  J=$(timeout 15 curl -s -H "Authorization: Bearer $KEY" https://api.deepseek.com/user/balance 2>/dev/null)
  unset KEY
  OUT=$(printf '%s' "$J" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
if not isinstance(d, dict) or "balance_infos" not in d:
    sys.exit(1)
b = (d.get("balance_infos") or [{}])[0]
cur = b.get("currency", "")
bal = b.get("total_balance", "")
if bal == "":
    sys.exit(1)
sym = {"CNY": "\u00a5", "USD": "$"}.get(cur, (cur + " ") if cur else "")
state = "\u53ef\u7528" if d.get("is_available") else "\u4e0d\u53ef\u7528\u00b7\u4f59\u989d\u4e0d\u8db3/\u6b20\u8d39"
print("%s%s\uff08%s\uff09" % (sym, bal, state))
' 2>/dev/null)
  if [ -n "$OUT" ]; then echo "$OUT"; exit 0; fi
fi

# 回退：无可用密钥或快照时，明确报不可用（不要从 status 文本猜数字）
echo "(暂不可用)"
