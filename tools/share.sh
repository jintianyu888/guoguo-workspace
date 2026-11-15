#!/bin/bash
# share.sh v1.0 — 大文件互传（无 30M 限制）
# 用法: share.sh start [目录] [端口]   share.sh stop   share.sh status
set -uo pipefail
DIR=${2:-/home/j/.openclaw/workspace/state/share}
PORT=${3:-18888}
TOKEN_FILE=/home/j/.config/fileshare.token
case ${1:-status} in
  start)
    mkdir -p "$DIR"; [ -f "$TOKEN_FILE" ] || openssl rand -hex 12 > "$TOKEN_FILE"; chmod 600 "$TOKEN_FILE"
    TOK=$(cat "$TOKEN_FILE")
    if [ -f "$HOME/.config/systemd/user/oc-fileshare.service" ]; then
      systemctl --user stop oc-fileshare.service 2>/dev/null
      systemctl --user start oc-fileshare.service
      sleep 1
      echo "目录: $DIR"; echo "端口: $PORT"; echo "（持久单元 oc-fileshare.service）"
      exit 0
    fi
    systemctl --user stop oc-fileshare.service 2>/dev/null
    systemd-run --user --unit=oc-fileshare --collect \
      -p WorkingDirectory="$DIR" \
      -p Environment=FS_TOKEN="$TOK" \
      /usr/bin/python3 /home/j/.openclaw/workspace/tools/fileshare.py "$DIR" "$PORT" >/dev/null 2>&1
    sleep 1
    echo "目录: $DIR"
    echo "局域网: http://192.168.1.108:$PORT/$TOK/"
    echo "Tailscale: http://100.109.128.37:$PORT/$TOK/"
    echo "本机: http://127.0.0.1:$PORT/$TOK/"
    ;;
  stop) systemctl --user stop oc-fileshare.service 2>/dev/null; echo stopped ;;
  info)
    TOK=$(cat "$TOKEN_FILE" 2>/dev/null)
    echo "文件站（token: $TOK）"
    echo "  局域网:   http://192.168.1.108:${PORT}/$TOK/"
    echo "  公网:     https://gy.taild2d30d.ts.net:8443/$TOK/"
    echo "  目录:     $DIR"
    echo "  换 token: openssl rand -hex 12 > $TOKEN_FILE && systemctl --user restart oc-fileshare"
    echo "  关闭公网: 'C:\Program Files\Tailscale\tailscale.exe' funnel --https=8443 off"
    ;;
  status) systemctl --user is-active oc-fileshare.service 2>/dev/null || echo inactive ;;
esac