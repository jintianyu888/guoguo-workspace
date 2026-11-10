#!/usr/bin/env bash
# proxy-check.sh —— 测 Windows 客户端的代理能否被 WSL 用（2026-10-03）
# 主公打开「局域网连接」后，WSL 即可通过 Windows 主机 IP 访问 127.0.0.1:7890
P=http://172.18.240.1:7890
echo '== 代理端口连通 =='
timeout 3 bash -c 'echo > /dev/tcp/172.18.240.1/7890' 2>/dev/null && echo '7890 可连 ✅' || echo '7890 不通 ❌（局域网连接还没开？）'
echo '== 走代理测国外 =='
for u in https://www.google.com https://www.bbc.com; do
  echo -n "$u: "; timeout 15 curl -s -x "$P" -o /dev/null -w '%{http_code}\n' "$u" 2>&1 || echo TIMEOUT
done
echo -n '出口IP(走代理): '; timeout 15 curl -s -x "$P" https://api.ipify.org 2>&1; echo
echo '== 直连对照 =='
echo -n '百度(直连): '; timeout 8 curl -s -o /dev/null -w '%{http_code}\n' https://www.baidu.com 2>&1