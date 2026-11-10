#!/usr/bin/env bash
# vpn-check.sh —— 检查 WSL 是否已能走 Windows 的 VPN（镜像网络模式后）2026-10-03
echo '== 网络模式/IP =='
ip -4 addr show eth0 2>/dev/null | grep -E 'inet ' | head -1
ip route 2>/dev/null | head -2
echo '== 国内对照 =='
echo -n 'baidu: '; timeout 8 curl -s -o /dev/null -w '%{http_code}\n' https://www.baidu.com 2>&1
echo '== 国外目标 =='
for u in https://www.google.com https://www.bbc.com https://www.dw.com https://rss.nytimes.com; do
  echo -n "$u: "; timeout 12 curl -s -o /dev/null -w '%{http_code}\n' "$u" 2>&1 || echo TIMEOUT
done
echo '== 出口 IP / 归属 =='
timeout 12 curl -s https://api.ipify.org 2>&1; echo
timeout 12 curl -s https://ipinfo.io/org 2>&1 | head -1