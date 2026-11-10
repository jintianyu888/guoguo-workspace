#!/bin/bash
# disk-cleanup-all.sh v3 —— DEHX 四盘统一清理（唯一入口）
# 2026-10-24 双审结论落地：deepseek-v4-pro=GO-WITH-FIXES(5项)、kimi-k3=NO-GO(5项)，两轮必改项全部合并：
#   1) conf 用「最后一个冒号」切分 + realpath -m 校验，杜绝路径含冒号被截断
#   2) ledger JSON 不再手工 printf 拼接，统一由 python json.dumps 生成（文件名含引号/反斜杠不会坏）
#   3) 删除前逐项 realpath 前缀校验（必须仍在白名单根目录之下），否则 REJECT 并记账
#   4) 两阶段：先生成 to-delete-*.tsv 清单，DRY=0 时只按该清单逐行删（删前二次校验存在+在白名单内）
#   5) flock 显式解锁 + fd 关闭
# 用法：DRY=1 干跑（默认，只出清单）/ DRY=0 真删 / AGE_MIN=180 覆盖回收站批次阈值
set -uo pipefail
W=/home/j/.openclaw/workspace
DRY=${DRY:-1}
CONF=${CONF:-$W/state/work/cleanup-targets.conf}
REPORT=$W/state/work/disk-cleanup-report.txt
LEDGER=$W/state/trash-ledger.jsonl
LOCK=$W/state/work/disk-cleanup.lock
STAMP=$(date +%Y%m%d-%H%M)
MANIFEST=$W/state/work/to-delete-$STAMP.tsv
STATUS=$W/state/work/to-delete-$STAMP.status
: > "$REPORT"; : > "$MANIFEST"; : > "$STATUS"
say(){ echo "$@" | tee -a "$REPORT"; }
human(){ numfmt --to=iec --suffix=B "${1:-0}" 2>/dev/null || echo "${1:-0}B"; }
bytes_of(){ du -sb "$1" 2>/dev/null | cut -f1; }
used_pct(){ df -h "/mnt/$1" 2>/dev/null | awk 'NR==2{print $5}'; }

exec 9>"$LOCK"
if ! flock -n 9; then say "另一个清理实例在跑，退出"; exec 9>&-; exit 0; fi

[ -f "$CONF" ] || { echo "缺少目标清单 $CONF"; exec 9>&-; exit 2; }
COUNT=0; TOTAL=0; SKIP=0; REJECT=0; DELETED=0
say "== 磁盘统一清理 v3 $(date '+%F %T')  DRY=$DRY =="
for d in d e h x; do say "   盘 $d: 已用 $(used_pct $d)"; done
say "   清单：$MANIFEST"

# ---------- 采集：白名单内的候选 ----------
collect(){ # $1=root  $2=分钟  $3=类型(trash|residue)
  local rp pmin kind; rp=$(realpath -m "$1" 2>/dev/null) || return 0
  pmin="$2"; kind="$3"
  [ -d "$rp" ] || return 0
  if [ "$kind" = "trash" ]; then
    find "$rp" -mindepth 1 -maxdepth 1 -mmin +"$pmin" 2>/dev/null | while IFS= read -r it; do
      r_it=$(realpath -m "$it" 2>/dev/null) || continue
      case "$r_it" in "$rp"/*) ;; *) echo "REJECT\t0\t$it" >> "$MANIFEST"; continue;; esac
      printf "%s\t%s\t%s\t%s\n" "$kind" "$rp" "$(bytes_of "$r_it")" "$r_it" >> "$MANIFEST"
    done
  else
    find "$rp" -maxdepth 6 -type f \( -name '*.tmp' -o -name '*.part' -o -name '*.stale' -o -name '*.crdownload' \) -mmin +"$pmin" 2>/dev/null | while IFS= read -r f; do
      r_f=$(realpath -m "$f" 2>/dev/null) || continue
      case "$r_f" in "$rp"/*) ;; *) echo "REJECT\t0\t$f" >> "$MANIFEST"; continue;; esac
      if command -v fuser >/dev/null 2>&1 && fuser "$r_f" >/dev/null 2>&1; then echo "SKIP\t0\t$r_f" >> "$MANIFEST"; continue; fi
      printf "%s\t%s\t%s\t%s\n" "$kind" "$rp" "$(bytes_of "$r_f")" "$r_f" >> "$MANIFEST"
    done
  fi
}

# ---- 两阶段：删除阶段可复用采集阶段已落地的清单 ----
SKIP_COLLECT=""
if [ -n "${MANIFEST_IN:-}" ]; then
  if [ "${MANIFEST_IN}" = "latest" ]; then
    SRC=$(ls -t "$W"/state/work/to-delete-*.tsv 2>/dev/null | head -1)
  else
    SRC="${MANIFEST_IN}"
  fi
  if [ -z "${SRC:-}" ] || [ ! -f "${SRC}" ]; then
    say "缺少采集清单（MANIFEST_IN=${MANIFEST_IN}），本次不删"
    timeout 30 sh $W/tools/notify.sh "⚠️ 统一清理：找不到采集清单，已跳过删除" >/dev/null 2>&1 || true
    flock -u 9; exec 9>&-; exit 3
  fi
  AGE_S=$(( $(date +%s) - $(stat -c %Y "${SRC}") ))
  if [ "$AGE_S" -gt 21600 ]; then
    say "采集清单已过期（${AGE_S}s > 6h），本次不删：${SRC}"
    timeout 30 sh $W/tools/notify.sh "⚠️ 统一清理：清单过期，已跳过删除" >/dev/null 2>&1 || true
    flock -u 9; exec 9>&-; exit 3
  fi
  cp -- "${SRC}" "$MANIFEST"
  SKIP_COLLECT=1
  say "   复用采集清单：${SRC}"
fi

if [ -z "${SKIP_COLLECT}" ]; then
say ""
say "-- [1/2] 采集（回收站批次 + 备份残骸） --"
while IFS= read -r line; do
  case "$line" in ''|'#'*) continue;; esac
  pmin="${line##*:}"; rest="${line%:*}"
  case "$pmin" in ''|*[!0-9]*) continue;; esac
  [ -n "${AGE_MIN:-}" ] && [ "${rest#residue:}" = "$rest" ] && pmin="$AGE_MIN"
  case "$rest" in
    residue:*) collect "${rest#residue:}" "$pmin" residue;;
    *)         collect "$rest" "$pmin" trash;;
  esac
done < "$CONF"
else
  say ""
  say "-- [1/2] 采集：跳过（复用既有清单） --"
fi

# ---------- 执行 / 报告 ----------
say ""
if [ "$DRY" = "1" ]; then
  while IFS=$'\t' read -r kind root size path; do
    case "$kind" in REJECT) say "  [REJECT] $path"; REJECT=$((REJECT+1)); continue;; SKIP) say "  [skip 占用] $path"; SKIP=$((SKIP+1)); continue;; esac
    say "  [would_delete] $(human "$size")\t$path"; COUNT=$((COUNT+1)); TOTAL=$((TOTAL+size))
  done < "$MANIFEST"
else
  while IFS=$'\t' read -r kind root size path; do
    case "$kind" in REJECT) printf 'REJECT\t%s\t0\tREJECT\n' "$path" >> "$STATUS"; REJECT=$((REJECT+1)); continue;; SKIP) printf 'SKIP\t%s\t0\tSKIP_BUSY\n' "$path" >> "$STATUS"; SKIP=$((SKIP+1)); continue;; esac
    [ -e "$path" ] || { printf 'GONE\t%s\t0\tGONE\n' "$path" >> "$STATUS"; continue; }
    r_p=$(realpath -m "$path" 2>/dev/null) || { printf 'REJECT\t%s\t0\tREJECT_REALPATH\n' "$path" >> "$STATUS"; REJECT=$((REJECT+1)); continue; }
    case "$r_p" in "$root"/*) ;; *) printf 'REJECT\t%s\t0\tREJECT_OUTSIDE\n' "$path" >> "$STATUS"; REJECT=$((REJECT+1)); continue;; esac
    if rm -rf -- "$r_p"; then printf 'DELETED\t%s\t%s\tOK\n' "$r_p" "$size" >> "$STATUS"; DELETED=$((DELETED+1)); COUNT=$((COUNT+1)); TOTAL=$((TOTAL+size)); say "  [deleted] $(human "$size")\t$r_p"
    else printf 'FAILED\t%s\t%s\tFAILED\n' "$r_p" "$size" >> "$STATUS"; say "  [failed ] $r_p"; fi
  done < "$MANIFEST"
fi

# ---------- 空目录 ----------
say ""
say "-- [3] 空回收站目录 --"
while IFS= read -r line; do
  case "$line" in ''|'#'*|residue:*) continue;; esac
  rp="${line%:*}"; rp=$(realpath -m "$rp" 2>/dev/null) || continue
  [ -d "$rp" ] || continue
  n=$(find "$rp" -mindepth 1 -maxdepth 1 -type d -empty 2>/dev/null | wc -l)
  if [ "$n" -gt 0 ]; then
    say "  [$( [ "$DRY" = 0 ] && echo cleaned || echo would_clean )] 空目录 $n 个 @ $rp"
    [ "$DRY" = "0" ] && find "$rp" -mindepth 1 -maxdepth 1 -type d -empty -delete 2>/dev/null
  fi
done < "$CONF"

# ---------- 记账（python 生成 JSON，杜绝手工拼接） ----------
python3 - "$STATUS" "$LEDGER" "$STAMP" <<'PY'
import json,sys,datetime
status,ledger,stamp=sys.argv[1:4]
now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
rows=[]
for line in open(status,encoding='utf-8',errors='replace'):
    p=line.rstrip('\n').split('\t')
    if len(p)<4: continue
    rows.append({"ts":now,"action":"cleanup_all","status":p[0],"path":p[1],"size":int(p[2] or 0),"note":p[3],"run":stamp})
if rows:
    with open(ledger,'a',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+'\n')
print("ledger +%d"%len(rows))
PY

say ""
say "== 合计：处理 $COUNT 项，$(human $TOTAL)，跳过占用 $SKIP，拒绝 $REJECT，实删 $DELETED（DRY=$DRY） =="
for d in d e h x; do say "   盘 $d: 已用 $(used_pct $d)"; done
timeout 30 sh $W/tools/notify.sh "🧹 磁盘统一清理(DRY=$DRY)：处理 $COUNT 项，约 $(human $TOTAL)，实删 $DELETED" >/dev/null 2>&1 || true
flock -u 9; exec 9>&-
exit 0
