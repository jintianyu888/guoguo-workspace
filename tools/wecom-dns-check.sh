#!/bin/bash
# 企微 funnel 公网 DNS 复查脚本
curl -s -m 15 'https://doh.pub/dns-query?name=openclaw-gy.taild2d30d.ts.net&type=A' -H 'accept: application/dns-json' > /home/j/.openclaw/workspace/state/tmp/wecom-dns-check.json 2>/dev/null
status=$(python3 -c "import json;d=json.load(open('/home/j/.openclaw/workspace/state/tmp/wecom-dns-check.json'));print(d.get('Status'))" 2>/dev/null)
answer=$(python3 -c "import json;d=json.load(open('/home/j/.openclaw/workspace/state/tmp/wecom-dns-check.json'));print(','.join([a.get('data','') for a in d.get('Answer',[]) if a.get('type')==1]))" 2>/dev/null)
if [ "$status" = "0" ] && [ -n "$answer" ]; then
  echo "✅ 公网 DNS 已生效，funnel 域名解析到：$answer"
  echo ""
  echo "老板现在可以回企业微信后台填回调 URL 保存了："
  echo "https://openclaw-gy.taild2d30d.ts.net/plugins/wecom/agent/default"
else
  echo "❌ 30 分钟复查：公网 DNS 仍解析不到 funnel 域名（状态 $status）"
  echo ""
  echo "建议去 Tailscale 管理后台 login.tailscale.com 查看 funnel / HTTPS 证书状态"
fi
