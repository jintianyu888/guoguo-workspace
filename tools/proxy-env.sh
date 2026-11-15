#!/bin/bash
# 代理环境（2026-11-15）：慢头云 127.0.0.1:7890 → netsh portproxy 0.0.0.0:7891 → WSL 可达
# 用法：source tools/proxy-env.sh   或   bash tools/proxy-env.sh --check
PROXY_HOST=${PROXY_HOST:-$(ip route | awk '/default/ {print $3; exit}')}
PROXY_PORT=${PROXY_PORT:-7891}
export http_proxy="http://$PROXY_HOST:$PROXY_PORT"
export https_proxy="$http_proxy"
export HTTP_PROXY="$http_proxy"
export HTTPS_PROXY="$http_proxy"
export no_proxy="localhost,127.0.0.1,::1,192.168.0.0/16,172.16.0.0/12,10.0.0.0/8,.cn,.aliyun.com,.deepseek.com,.feishu.cn,.larksuite.com"
export NO_PROXY="$no_proxy"
if [ "${1:-}" = "--check" ]; then
  timeout 12 curl -s -o /dev/null -w "google=%{http_code} " https://www.google.com && echo "proxy OK ($http_proxy)" || echo "proxy FAIL"
fi
