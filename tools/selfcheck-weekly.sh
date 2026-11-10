#!/bin/bash
# selfcheck-weekly.sh — 每周记忆/配置体检（零 token）：备份配置 + doctor + 关键文件指纹
W=/home/j/.openclaw; O=$W/workspace/state/selfcheck-weekly.md; TS=$(date +%F_%H%M)
{
echo "# 每周体检 $(date '+%F %T')"
echo
echo '## 1) 配置备份'
cp -n $W/openclaw.json $W/openclaw.json.bak-$TS 2>/dev/null && echo "- 已备份 openclaw.json.bak-$TS"
echo "- 现有备份: $(ls -1 $W/openclaw.json.bak* 2>/dev/null | wc -l) 份"
echo
echo '## 2) 规矩文件指纹（防意外改动）'
cd $W/workspace || exit 1
for f in AGENTS.md USER.md MEMORY.md; do [ -f $f ] && echo "- $f  $(wc -l < $f) 行  sha=$(sha256sum $f | cut -c1-12)"; done
echo
echo '## 3) 压缩/记忆刷新配置'
openclaw config get messages.responseUsage 2>&1 | head -n 1 | sed 's/^/- responseUsage: /'
openclaw config get messages.queue 2>&1 | head -n 1 | sed 's/^/- queue: /'
echo
echo '## 4) 健康检查'
timeout 90 openclaw doctor 2>&1 | tail -n 10 | sed 's/^/- /'
} > $O 2>&1
echo ""; echo "报告: $O"