#!/bin/bash
# 把已加密存储的企微凭据写入配置明文（值不打印）
set -uo pipefail
T="${WECOM_CALLBACK_TOKEN:-}"; A="${WECOM_ENCODING_AES_KEY:-}"
if [ -z "$T" ] || [ -z "$A" ]; then echo "❌ env 未注入密钥（token ${#T} / aeskey ${#A}），不写配置"; exit 1; fi
echo "· 注入校验：token ${#T} 位 · aeskey ${#A} 位"
TT="$T" AA="$A" python3 -c 'import json,os;print(json.dumps({"channels":{"wecom":{"agent":{"token":os.environ["TT"],"encodingAESKey":os.environ["AA"]}}}},ensure_ascii=False))' | openclaw config patch --stdin >/dev/null 2>&1 && echo "✅ config 已写入明文（token / encodingAESKey）" || echo "⚠️ config patch 失败"
python3 -c 'import json;d=json.load(open("/home/j/.openclaw/openclaw.json"));a=d["channels"]["wecom"]["agent"];print("· 配置校验长度：token",len(a["token"]),"· aeskey",len(a["encodingAESKey"]))'
echo "=== 渠道状态 ==="
timeout 45 openclaw channels status 2>&1 | grep -iE "企业微信|wecom" | head -3
