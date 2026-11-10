#!/usr/bin/env bash
# with-proxy.sh —— 需要外网时用它包一层（2026-10-03 主公令：代理常开、直接用）
# 用法： tools/with-proxy.sh <命令...>      例： tools/with-proxy.sh curl -I https://github.com
# 铁律：只给需要外网的活加代理；飞书/群晖/密钥/国内服务 一律不要用这个包。
P=http://172.18.240.1:7890
if ! timeout 2 bash -c 'echo > /dev/tcp/172.18.240.1/7890' 2>/dev/null; then
  echo "[with-proxy] 代理 172.18.240.1:7890 不通 —— 直连执行（结果可能是国内源/失败）" >&2
  exec "$@"
fi
export http_proxy="$P" https_proxy="$P" all_proxy="$P"
export HTTP_PROXY="$P" HTTPS_PROXY="$P" ALL_PROXY="$P"
export no_proxy="localhost,127.0.0.1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12,*.local"
export NO_PROXY="$no_proxy"
exec "$@"