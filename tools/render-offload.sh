#!/usr/bin/env bash
# render-offload.sh —— 把视频编码卸载到 B 机（RX 9070 XT / AMD AMF）
# 依赖：B 的 D 盘共享已挂到 /mnt/b（//192.168.1.107/D）
# 用法：
#   bash tools/render-offload.sh check
#   bash tools/render-offload.sh submit --in /mnt/b/media/in.mp4 --out /mnt/b/media/out.mp4 --codec hevc --cq 23
#   bash tools/render-offload.sh status <jobid>
#   bash tools/render-offload.sh wait <jobid>
#   bash tools/render-offload.sh list
set -uo pipefail
ROOT="${B_RENDER_ROOT:-/mnt/b/render}"
Q="$ROOT/queue"; W="$ROOT/work"; O="$ROOT/out"; L="$ROOT/log"

die(){ echo "✗ $*" >&2; exit 1; }

need_mount(){
  [ -d "$ROOT" ] || die "B 机渲染目录不可见：$ROOT 未挂载。先挂：mount -t cifs //192.168.1.107/D /mnt/b -o username=<用户>,password=<密码>,uid=1000,gid=1000,iocharset=utf8"
}

cmd="${1:-}"; shift || true

case "$cmd" in
  check)
    need_mount
    echo "✓ 渲染目录可用：$ROOT"
    for d in "$Q" "$W" "$O" "$L"; do [ -d "$d" ] && echo "  - $(basename "$d") ok" || echo "  - $(basename "$d") 缺失"; done
    if [ -f "$L/worker.log" ]; then echo "  worker 最近日志："; tail -3 "$L/worker.log" | sed 's/^/    /'; else echo "  ⚠ 没有 worker.log —— B 机 worker 可能没跑"; fi
    ;;

  submit)
    IN=""; OUT=""; CODEC="hevc"; CQ="23"; EXTRA=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --in) IN="$2"; shift 2;;
        --out) OUT="$2"; shift 2;;
        --codec) CODEC="$2"; shift 2;;
        --cq) CQ="$2"; shift 2;;
        --extra) EXTRA="$2"; shift 2;;
        *) die "未知参数 $1";;
      esac
    done
    [ -n "$IN" ] && [ -n "$OUT" ] || die "用法：submit --in <输入> --out <输出> [--codec hevc|av1|h264] [--cq 23]"
    need_mount
    case "$CODEC" in
      hevc) VENC="hevc_amf";;
      av1)  VENC="av1_amf";;
      h264) VENC="h264_amf";;
      copy) VENC="";;
      *) die "codec 只支持 hevc/av1/h264/copy";;
    esac
    ID="$(date +%Y%m%d-%H%M%S)-$$"
    QDIR="$Q" JID="$ID" SRC="$IN" DST="$OUT" VENC="$VENC" CQ="$CQ" EXTRA="$EXTRA" python3 - <<'PY'
import json,os
jid=os.environ["JID"]; src=os.environ["SRC"]; dst=os.environ["DST"]
venc=os.environ["VENC"]; cq=os.environ["CQ"]; extra=os.environ.get("EXTRA","")
def win(p):
    return "D:/video"+p[len("/mnt/b"):] if p.startswith("/mnt/b") else p
src=win(src); dst=win(dst)
args=["-i",src]
if venc:
    args+=["-c:v",venc]
    if "amf" in venc:
        args+=["-quality","quality","-rc","cqp","-qp_i",cq,"-qp_p",cq]
else:
    args+=["-c:v","copy"]
args+=["-c:a","aac","-b:a","192k","-movflags","+faststart"]
if extra: args+=extra.split()
args+=[dst]
p=os.path.join(os.environ["QDIR"],jid+".json")
open(p,"w").write(json.dumps({"id":jid,"args":args},ensure_ascii=False))
print(jid)
PY
    ;;

  status)
    JID="${1:-}"; [ -n "$JID" ] || die "用法：status <jobid>"
    need_mount
    [ -f "$W/$JID.done" ] && { echo "完成："; cat "$W/$JID.done"; }
    [ -f "$W/$JID.progress" ] && tail -2 "$W/$JID.progress"
    [ -f "$L/$JID.log" ] && tail -3 "$L/$JID.log"
    [ -f "$W/$JID.json" ] && echo "状态：运行中"
    [ -f "$Q/$JID.json" ] && echo "状态：排队中"
    ;;

  wait)
    JID="${1:-}"; [ -n "$JID" ] || die "用法：wait <jobid>"
    need_mount
    i=0
    while [ $i -lt 240 ]; do
      if [ -f "$W/$JID.done" ]; then echo "✓ $JID 完成"; cat "$W/$JID.done"; exit 0; fi
      sleep 5; i=$((i+1))
    done
    echo "⚠ 20 分钟未完成，仍在跑：$JID"; exit 1
    ;;

  list)
    need_mount
    echo "排队："; ls -1 "$Q" 2>/dev/null | sed 's/\.json$//' | sed 's/^/  /'
    echo "运行："; ls -1 "$W"/*.json 2>/dev/null | xargs -r -n1 basename | sed 's/\.json$//' | sed 's/^/  /'
    ;;

  *)
    sed -n '2,9p' "$0"; exit 1;;
esac
