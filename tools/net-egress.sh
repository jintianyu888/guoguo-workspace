#!/usr/bin/env bash
# net-egress.sh — 判断 WSL 外网出口 / 找 Windows 侧代理 / 给下载套代理
# 用法: net-egress.sh {status|env|test [URL...]}
set -uo pipefail

WINIP="$(ip route | awk '/^default/{print $3; exit}')"
PORTS="${NET_PORTS:-7890 7891 1080 10808 2080}"
PROXY=""

probe_proxy() {
  local ip="$1" p
  for p in $PORTS; do
    if timeout 1 bash -c "echo > /dev/tcp/$ip/$p" 2>/dev/null; then
      if curl -s -x "http://$ip:$p" --max-time 6 -o /dev/null -w '%{http_code}' https://ipinfo.io/ip 2>/dev/null | grep -qE '^[0-9]{3}$'; then
        PROXY="http://$ip:$p"; return 0
      fi
    fi
  done
  return 1
}

cmd_status() {
  echo "WSL 网关(Windows) = $WINIP"
  printf 'WSL 出口 IP: '; curl -s --max-time 8 https://ipinfo.io/ip 2>/dev/null || printf '(取不到)'
  echo
  if probe_proxy "$WINIP"; then
    echo "代理: 可用 $PROXY"
    printf '代理出口 IP: '; curl -s -x "$PROXY" --max-time 8 https://ipinfo.io/ip 2>/dev/null; echo
  else
    echo "代理: 不可达（Clash 未开「允许局域网连接」，或端口不在 $PORTS）"
  fi
  echo "提示: 让 WSL 继承 VPN 需 .wslconfig 加 networkingMode=mirrored 并 wsl --shutdown"
}

cmd_env() {
  if probe_proxy "$WINIP"; then
    echo "export http_proxy=$PROXY https_proxy=$PROXY all_proxy=$PROXY"
    echo "export HTTP_PROXY=$PROXY HTTPS_PROXY=$PROXY ALL_PROXY=$PROXY"
    echo "export no_proxy=127.0.0.1,localhost,192.168.0.0/16,172.16.0.0/12"
  else
    echo "# 代理不可达，未导出（直连模式）" >&2
    return 1
  fi
}

cmd_test() {
  local urls=("$@")
  [ ${#urls[@]} -eq 0 ] && urls=(https://github.com https://huggingface.co https://registry.ollama.ai https://pypi.org https://registry.npmjs.org)
  probe_proxy "$WINIP" || echo "代理不可达，仅测直连"
  printf '%-44s %-16s %-16s\\n' URL 直连 代理
  local u d p
  for u in "${urls[@]}"; do
    d=$(curl -s -o /dev/null --max-time 10 -r 0-2000000 -w '%{http_code}/%{speed_download}' "$u" 2>/dev/null)
    p="—"
    [ -n "$PROXY" ] && p=$(curl -s -x "$PROXY" -o /dev/null --max-time 10 -r 0-2000000 -w '%{http_code}/%{speed_download}' "$u" 2>/dev/null)
    printf '%-44s %-16s %-16s\\n' "$u" "$d" "$p"
  done
  echo "（B/s；000 = 不通）"
}


cmd_run() {
  if [ $# -eq 0 ]; then echo "用法: $0 run <命令...>" >&2; exit 2; fi
  if ! probe_proxy "$WINIP"; then echo "代理不可达，直连执行" >&2; exec "$@"; fi
  echo "[net] 走代理 $PROXY" >&2
  http_proxy="$PROXY" https_proxy="$PROXY" all_proxy="$PROXY"   HTTP_PROXY="$PROXY" HTTPS_PROXY="$PROXY" ALL_PROXY="$PROXY"   no_proxy="127.0.0.1,localhost,192.168.0.0/16,172.16.0.0/12,10.0.0.0/8"   exec "$@"
}

case "${1:-status}" in
  status) cmd_status ;;
  env) cmd_env ;;
  test) shift; cmd_test "$@" ;;
  run) shift; cmd_run "$@" ;;
  *) echo "用法: $0 {status|env|test [URL...]|run <命令...>}"; exit 2 ;;
esac
