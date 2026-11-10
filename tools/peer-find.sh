#!/bin/bash
# peer-find.sh — 局域网设备自动寻址：IP 变了也能找到（2026-11-01 主公令）
# 用法: peer-find.sh <名字> [--refresh] [--json] [--timeout N]
# 注册表: state/peers.json（首次运行自动建）
# 寻址顺序: 缓存 IP → 候选列表 → 全段扫描（按端口+指纹匹配，不靠 IP）
set -uo pipefail
WS=/home/j/.openclaw/workspace
REG=$WS/state/peers.json
LOG=$WS/state/work/peer-find.log
NAME=${1:-}; shift || true
REFRESH=0; JSONOUT=0; TMO=2
for a in "$@"; do case "$a" in --refresh) REFRESH=1;; --json) JSONOUT=1;; --timeout) shift; TMO=${1:-2};; esac; done

log(){ printf '%s %s\n' "$(date -Iseconds)" "$*" >> "$LOG"; }
die(){ echo "ERR $*" >&2; exit 2; }
[ -n "$NAME" ] || die "用法: peer-find.sh <名字> [--refresh] [--json]"

if [ ! -f "$REG" ]; then
  cat > "$REG" <<'JSON'
{
  "ollama": {"port": 11434, "probe": "/api/tags", "match": "models", "last_ip": ""},
  "gateway": {"port": 18789, "probe": "/health", "match": "", "last_ip": ""},
  "nas": {"port": 22, "probe": "", "match": "", "last_ip": ""}
}
JSON
fi

cfg(){ python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));p=d.get(sys.argv[2]);print(json.dumps(p) if p else "")' "$REG" "$NAME"; }
PJ=$(cfg) || die "注册表读不了"
[ -n "$PJ" ] || die "未登记的设备: $NAME"
PORT=$(echo "$PJ" | python3 -c 'import json,sys;print(json.load(sys.stdin)["port"])')
PROBE=$(echo "$PJ" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("probe",""))')
MATCHP=$(echo "$PJ" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("match",""))')
CACHED=$(echo "$PJ" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("last_ip",""))')

verify(){  # $1=ip  → 0 真命中
  local ip=$1 out
  if [ -z "$PROBE" ]; then
    nc -z -w "$TMO" "$ip" "$PORT" >/dev/null 2>&1 && return 0 || return 1
  fi
  out=$(curl -s --max-time "$TMO" "http://$ip:$PORT$PROBE" 2>/dev/null)
  [ -n "$out" ] || return 1
  if [ -n "$MATCHP" ]; then echo "$out" | grep -q "$MATCHP" || return 1; fi
  return 0
}

save(){  # $1=ip
  python3 - "$REG" "$NAME" "$1" <<'PY'
import json,sys,os,time
reg,name,ip=sys.argv[1],sys.argv[2],sys.argv[3]
d=json.load(open(reg))
d.setdefault(name,{})
d[name]['last_ip']=ip
d[name]['last_seen']=time.strftime('%Y-%m-%dT%H:%M:%S%z')
tmp=reg+'.tmp'
open(tmp,'w').write(json.dumps(d,ensure_ascii=False,indent=2))
os.replace(tmp,reg)
PY
}

emit(){  # $1=ip  $2=来源
  save "$1"
  log "FOUND name=$NAME ip=$1 via=$2 port=$PORT"
  if [ $JSONOUT -eq 1 ]; then
    printf '{"name":"%s","ip":"%s","port":%s,"via":"%s"}\n' "$NAME" "$1" "$PORT" "$2"
  else
    echo "$1"
  fi
  exit 0
}

# 1) 缓存
if [ $REFRESH -eq 0 ] && [ -n "$CACHED" ] && verify "$CACHED"; then emit "$CACHED" cache; fi

# 2) 本机所在 /24（以 Windows 内网 IP 为准）
SUBNET=$(/mnt/c/Windows/System32/ipconfig.exe 2>/dev/null | iconv -f GBK -t UTF-8 2>/dev/null | grep -oE '192\.168\.[0-9]+\.[0-9]+' | head -1 | cut -d. -f1-3)
[ -n "$SUBNET" ] || SUBNET=192.168.1

# 3) 全段扫描（并行探端口，命中再验指纹）
HITS=$(seq 1 254 | xargs -P 64 -I{} sh -c "nc -z -w $TMO $SUBNET.{} $PORT >/dev/null 2>&1 && echo $SUBNET.{}" 2>/dev/null)
for ip in $HITS; do
  [ "$ip" = "$CACHED" ] && [ $REFRESH -eq 0 ] && continue
  if verify "$ip"; then emit "$ip" scan; fi
done

log "MISS name=$NAME port=$PORT subnet=$SUBNET"
echo "ERR 没找到 $NAME（端口 $PORT，网段 $SUBNET.*）" >&2
exit 1
