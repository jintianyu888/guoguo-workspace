#!/bin/bash
# 企业微信凭据安全录入：不回显、不进聊天、不出现在命令行
set -uo pipefail
echo "=== 企业微信凭据录入（输入时不会显示，粘上去就行）==="
printf '① Token: '; read -rs TOK; echo
[ -n "$TOK" ] || { echo "❌ Token 为空，已退出，什么都没写"; exit 1; }
printf '② EncodingAESKey: '; read -rs AES; echo
[ -n "$AES" ] || { echo "❌ EncodingAESKey 为空，已退出，什么都没写"; exit 1; }
printf "%s" "$TOK" | openclaw secrets store set WECOM_CALLBACK_TOKEN --value-file - >/dev/null 2>&1 && echo "✅ secrets store: WECOM_CALLBACK_TOKEN" || echo "⚠️ store Token 写入失败"
printf "%s" "$AES" | openclaw secrets store set WECOM_ENCODING_AES_KEY --value-file - >/dev/null 2>&1 && echo "✅ secrets store: WECOM_ENCODING_AES_KEY" || echo "⚠️ store AESKey 写入失败"
TOK="$TOK" AES="$AES" python3 -c "import json,os;print(json.dumps({'channels':{'wecom':{'agent':{'token':os.environ['TOK'],'encodingAESKey':os.environ['AES']}}}},ensure_ascii=False))" | openclaw config patch --stdin >/dev/null 2>&1 && echo "✅ config: channels.wecom.agent.token / .encodingAESKey 已写(明文)" || echo "⚠️ config patch 失败"
unset TOK AES
echo "=== 验证 ==="
printf "· Token 长度(脱敏校验): "; python3 -c "import json;d=json.load(open('/home/j/.openclaw/openclaw.json'));print(len(d['channels']['wecom']['agent']['token']))" 2>/dev/null || echo "?"
printf "· AESKey 长度(脱敏校验): "; python3 -c "import json;d=json.load(open('/home/j/.openclaw/openclaw.json'));print(len(d['channels']['wecom']['agent']['encodingAESKey']))" 2>/dev/null || echo "?"
timeout 40 openclaw channels status 2>&1 | grep -iE "企业微信|wecom" | head -3
echo "（若仍显示 SETUP，等几秒热重载；若报 encodingAESKey.trim is not a function，说明写成了非字符串）"
