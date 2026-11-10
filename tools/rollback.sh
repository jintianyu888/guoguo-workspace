#!/usr/bin/env bash
# rollback.sh —— 统一回档登记表（主公 2026-11-06 令：所有操作都要可以回档）
# 用法：
#   rollback.sh add <文件绝对路径> [说明]      # 改文件前登记：快照 + 记 SHA256
#   rollback.sh list [N]                       # 最近 N 条（默认 20）
#   rollback.sh undo <id>                      # 回档：当前文件另存 .pre-undo，再还原快照
set -uo pipefail
RB=/home/j/.openclaw/workspace/state/rollback
IDX=$RB/index.jsonl
mkdir -p "$RB"
cmd=${1:-list}

sha() { sha256sum "$1" 2>/dev/null | awk '{print $1}'; }

case "$cmd" in
  add)
    f=${2:?用法: rollback.sh add <文件> [说明]}
    note=${3:-}
    [ -e "$f" ] || { echo "文件不存在: $f"; exit 2; }
    ts=$(date +%Y%m%d-%H%M%S)
    id="rb-$ts-$(basename "$f" | tr -c 'A-Za-z0-9._-' '_')"
    snap="$RB/$id.snapshot"
    cp -p "$f" "$snap" || { echo "快照失败"; exit 3; }
    ok=$([ "$(sha "$f")" = "$(sha "$snap")" ] && echo 1 || echo 0)
    [ "$ok" = "1" ] || { echo "快照校验失败"; exit 4; }
    python3 - "$IDX" "$id" "$f" "$snap" "$(sha "$f")" "$note" <<'PY'
import json,sys,datetime
idx,id,f,snap,h,note=sys.argv[1:7]
rec={"id":id,"file":f,"snapshot":snap,"sha256":h,"note":note,
     "at":datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"status":"active"}
open(idx,"a").write(json.dumps(rec,ensure_ascii=False)+"\n")
print("已登记 %s  %s" % (id,f))
PY
    ;;
  list)
    n=${2:-20}
    [ -s "$IDX" ] || { echo "暂无登记"; exit 0; }
    python3 - "$IDX" "$n" <<'PY'
import json,sys
idx,n=sys.argv[1],int(sys.argv[2])
rows=[json.loads(l) for l in open(idx) if l.strip()][-n:]
for r in rows:
    print("%-52s %s  %s  %s" % (r["id"][:52], r["at"], r["status"], r["file"]))
PY
    ;;
  adopt)
    # 已改动文件用已有备份登记：adopt <原文件> <备份文件> [说明]
    f=${2:?}; bak=${3:?}; note=${4:-}
    [ -e "$f" ] && [ -e "$bak" ] || { echo "文件缺失"; exit 2; }
    ts=$(date +%Y%m%d-%H%M%S)
    id="rb-$ts-$(basename "$f" | tr -c 'A-Za-z0-9._-' '_')"
    cp -p "$bak" "$RB/$id.snapshot" || exit 3
    python3 - "$IDX" "$id" "$f" "$RB/$id.snapshot" "$(sha "$bak")" "$note" <<'PY'
import json,sys,datetime
idx,id,f,snap,h,note=sys.argv[1:7]
open(idx,"a").write(json.dumps({"id":id,"file":f,"snapshot":snap,"sha256":h,"note":note,
 "at":datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"status":"active"},ensure_ascii=False)+"\n")
print("已登记(已有备份) %s -> %s" % (id,f))
PY
    ;;
  undo)
    id=${2:?用法: rollback.sh undo <id>}
    python3 - "$IDX" "$id" <<'PY'
import json,sys,os,shutil,hashlib,datetime
idx,i=sys.argv[1],sys.argv[2]
rows=[json.loads(l) for l in open(idx) if l.strip()]
rec=next((r for r in rows if r["id"]==i),None)
if not rec: print("找不到记录:",i); sys.exit(2)
snap=rec["snapshot"]
if not os.path.exists(snap): print("快照丢失:",snap); sys.exit(3)
h=hashlib.sha256(open(snap,'rb').read()).hexdigest()
if h!=rec["sha256"]: print("快照 SHA256 不符，拒绝回档:",h); sys.exit(4)
if os.path.exists(rec["file"]):
    bak=rec["file"]+".pre-undo-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(rec["file"],bak); print("当前版本另存:",bak)
shutil.copy2(snap,rec["file"]); print("已回档:",rec["file"])
rec["status"]="undone"; rec["undone_at"]=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
open(idx,"w").write("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in rows))
PY
    ;;
  *) echo "用法: rollback.sh {add <文件> [说明] | list [N] | undo <id>}"; exit 1;;
esac
