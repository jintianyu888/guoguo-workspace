#!/bin/sh
# 夜间批量 OCR/ASR 归档（闲时 02:00 跑，由 cron 用 sh 调用，须 POSIX 兼容）
# 扫描媒体目录：图片/PDF -> tools/ocr-file，音频 -> tools/asr
# 结果写同名 .txt（放在文件旁边），并追加索引到 state/extract-index.jsonl
#
# 用法:
#   tools/batch-extract.sh [--dry-run] [--max N] [-v] [目录或文件...]
# 默认扫描 media/inbound 与 data/；单个文件可直接作为参数传入。
#
# 幂等 + 去重：已有同名且非空的 .txt 跳过；单次最多处理 --max（默认 50）个。
# 出错记录并继续，不中断整批；每文件间 sleep 限流。

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$(cd "$SCRIPT_DIR/.." && pwd)"
OCR="$SCRIPT_DIR/ocr-file"
ASR="$SCRIPT_DIR/asr"
INDEX="$WORKSPACE/state/extract-index.jsonl"
LOCK="$WORKSPACE/state/.batch-extract.lock"

MAX=50
DRY=0
VERBOSE=0
SLEEP="${BATCH_EXTRACT_SLEEP:-1}"
HAVE_POS=0

usage() {
  cat <<'EOF'
用法: batch-extract.sh [--dry-run] [--max N] [-v] [目录或文件...]
  --dry-run  只列出会处理哪些文件，不真正执行
  --max N    单次最多处理 N 个（默认 50）
  -v         详细输出（含跳过项）
  默认扫描 media/inbound 与 data/；也可传入具体目录或文件路径。
EOF
}

mkdir -p "$WORKSPACE/state"
tmp="$(mktemp)"
logf="$(mktemp)"
trap 'rm -f "$tmp" "$logf"' EXIT

add_dir() {
  find "$1" -type f 2>/dev/null >> "$tmp"
}

add_arg() {
  HAVE_POS=1
  if [ -d "$1" ]; then
    add_dir "$1"
  elif [ -f "$1" ]; then
    echo "$1" >> "$tmp"
  else
    echo "跳过不存在路径: $1" >&2
  fi
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --max) MAX="${2:?需要数值}"; shift 2 ;;
    --max=*) MAX="${1#*=}"; shift ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    -*) echo "未知参数: $1" >&2; usage >&2; exit 2 ;;
    *) add_arg "$1"; shift ;;
  esac
done

# -- 之后的剩余参数全部当作路径
for a in "$@"; do
  add_arg "$a"
done

if [ "$HAVE_POS" -eq 0 ]; then
  add_dir "$WORKSPACE/media/inbound"
  add_dir "$WORKSPACE/data"
fi

sort -u "$tmp" -o "$tmp"

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK"
  if ! flock -n 9; then echo "已有 batch-extract 在运行，本次退出" >&2; exit 0; fi
fi

lext() { printf '%s' "${1##*.}" | tr 'A-Z' 'a-z'; }

kind_of() {
  case "$(lext "$1")" in
    jpg|jpeg|png|webp|bmp|tif|tiff|pdf) echo ocr ;;
    ogg|mp3|wav|m4a|flac|opus|aac|amr|mka|wma) echo asr ;;
    *) echo "" ;;
  esac
}

count=0; okn=0; failn=0; skipn=0; nospeech=0

while IFS= read -r f; do
  [ -z "$f" ] && continue
  kind="$(kind_of "$f")"
  [ -z "$kind" ] && continue

  # 2026-10-17：扩展名会骗人（如 index.jsonl.mp3 实为文本），用真实 MIME 再验一次
  if command -v file >/dev/null 2>&1; then
    mt="$(file -b --mime-type "$f" 2>/dev/null || echo unknown)"
    case "$kind|$mt" in
      ocr\|image/*|ocr\|application/pdf) : ;;
      asr\|audio/*|asr\|video/*) : ;;
      *\|unknown) : ;;
      *) echo "跳过(扩展名与内容不符 $mt): $f" >&2
         printf '{"path":"%s","kind":"%s","ok":false,"ms":0,"ts":%s,"chars":0,"note":"mime-mismatch"}\n' "$f" "$kind" "$(date +%s)" >> "$INDEX"
         skipn=$((skipn+1)); count=$((count+1)); continue ;;
    esac
  fi

  dir="$(dirname "$f")"
  base="$(basename "$f")"
  name="${base%.*}"
  txt="$dir/$name.txt"

  if [ -f "$txt" ] && [ -s "$txt" ]; then
    [ "$VERBOSE" = 1 ] && echo "跳过(已有 txt): $f"
    skipn=$((skipn+1))
    continue
  fi

  if [ "$count" -ge "$MAX" ]; then
    echo "已达单次上限 $MAX，本批停止"
    break
  fi

  if [ "$DRY" = 1 ]; then
    echo "[dry-run] $kind  $f"
    count=$((count+1))
    continue
  fi

  t0=$(date +%s%3N); rc=1
  : > "$logf"
  if [ "$kind" = "ocr" ]; then
    nice -n 10 "$OCR" "$f" --out "$txt" >"$logf" 2>&1
    rc=$?
  else
    # 2026-09-29：默认走 GPU（已可用）；失败自动回落 CPU/int8，保证无人值守也不失败
    nice -n 10 "$ASR" "$f" --output_dir "$dir" --output_format txt >"$logf" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
      echo "GPU 分支失败(rc=$rc)，回落 CPU 重试" >>"$logf"
      ASR_FORCE_CPU=1 nice -n 10 "$ASR" "$f" --output_dir "$dir" --output_format txt >>"$logf" 2>&1
      rc=$?
    fi
  fi
  t1=$(date +%s%3N); ms=$((t1-t0))

  ok="false"; chars=0
  if [ "$rc" -eq 0 ] && [ -f "$txt" ] && [ -s "$txt" ]; then
    ok="true"
    chars="$(wc -m < "$txt" | tr -d ' ')"
    okn=$((okn+1))
  elif [ "$rc" -eq 0 ]; then
    # 2026-10-17：转写成功但没内容（静音/无人声），属正常，不计失败
    nospeech=$((nospeech+1))
    echo "SKIP(无内容): $f" >&2
  else
    failn=$((failn+1))
    echo "FAIL(rc=$rc): $f" >&2
    tail -n 5 "$logf" >&2 2>/dev/null || true
  fi

  ts="$(date +%s)"
  printf '{"path":"%s","kind":"%s","ok":%s,"ms":%s,"ts":%s,"chars":%s}\n' "$f" "$kind" "$ok" "$ms" "$ts" "$chars" >> "$INDEX"

  echo "[$kind] $ok ${ms}ms chars=$chars  $f"
  count=$((count+1))
  [ "$SLEEP" -gt 0 ] && sleep "$SLEEP"
done < "$tmp"

echo "=== 汇总: 处理 $count · 成功 $okn · 无内容 $nospeech · 失败 $failn · 跳过 $skipn ==="
