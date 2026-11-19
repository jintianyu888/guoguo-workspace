#!/bin/bash
# pkg-upgrade-gate.sh —— 双审通过后才逐包升级，失败回滚，自动出报告
# 由 pkg-upgrade-gate.timer 在 03:20（网关静默窗重启之后）触发
set -uo pipefail
W=/home/j/.openclaw/workspace
LOG=$W/state/work/pkgup-gate.log
CSV=$W/state/work/pkgup-20261029.csv
REP=$W/state/work/pkg-upgrade-report-20261029.md
PROMPT=$W/state/work/pkgup-plan.txt
mkdir -p "$W/state/work"
exec >>"$LOG" 2>&1
echo "=== $(date '+%F %T') 开始 ==="

# 1) 等网关健康
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:18789/health || true)
  [ "$code" = "200" ] && break
  sleep 10
done

# 2) 双审
D=$W/state/work/cross-review/$(date +%Y%m%d-%H%M%S)
mkdir -p "$D"
bash $W/tools/cross-review.sh --n 2 --prompt-file "$PROMPT" >/dev/null 2>&1 || true
LATEST=$(ls -td $W/state/work/cross-review/*/ 2>/dev/null | head -1)
OK=0; VETO=0
for f in "$LATEST"*.txt; do
  [ -f "$f" ] || continue
  sz=$(stat -c%s "$f")
  [ "$sz" -lt 80 ] && continue
  OK=$((OK+1))
  grep -qiE "NO-GO" "$f" && VETO=1
done
echo "评审：有效 $OK 份，否决=$VETO（目录 $LATEST）"
if [ "$OK" -lt 2 ] || [ "$VETO" -eq 1 ]; then
  bash $W/tools/notify.sh --alert "依赖升级已跳过：双审未通过（有效 $OK 份，否决 $VETO）" || true
  exit 1
fi

# 3) 逐包升级（补丁级优先，主版本靠后）
ASR=$W/tools/asr-venv; EMB=$W/tools/embed-venv
T_ASR='$ASR/bin/python3 -c "import av,ctranslate2,faster_whisper;print(1)"'
T_EMB='$EMB/bin/python3 -c "import fastembed,onnxruntime;print(1)"'
: > "$CSV"
for p in brotli certifi ctranslate2 filelock hf-xet onnxruntime playwright pycryptodomex pypdfium2 yt-dlp; do
  bash $W/tools/pkg-upgrade-one.sh "$ASR" "$p" "$ASR/bin/python3 -c 'import sys'" || { echo "ASR 在 $p 停下"; break; }
done
bash $W/tools/pkg-upgrade-one.sh "$ASR" 'pyee' '$W/tools/asr-venv/bin/python3 -c "import pyee"' || true
bash $W/tools/pkg-upgrade-one.sh "$ASR" 'huggingface_hub' '$W/tools/asr-venv/bin/python3 -c "import huggingface_hub"' || true
bash $W/tools/pkg-upgrade-one.sh "$ASR" 'av' '$W/tools/asr-venv/bin/python3 -c "import av;print(av.__version__)"' || true
for p in certifi filelock hf-xet httpcore2 httpx2 nvidia-cublas nvidia-cudnn-cu13 onnxruntime onnxruntime-gpu wheel setuptools; do
  bash $W/tools/pkg-upgrade-one.sh "$EMB" "$p" "$EMB/bin/python3 -c 'import sys'" || { echo "EMB 在 $p 停下"; break; }
done
bash $W/tools/pkg-upgrade-one.sh "$EMB" 'pyee' '$W/tools/embed-venv/bin/python3 -c "import pyee"' || true
bash $W/tools/pkg-upgrade-one.sh "$EMB" 'huggingface_hub' '$W/tools/embed-venv/bin/python3 -c "import huggingface_hub"' || true
bash $W/tools/pkg-upgrade-one.sh "$EMB" 'fastembed' '$W/tools/embed-venv/bin/python3 -c "import fastembed;print(fastembed.__version__)"' || true
bash $W/tools/pkg-upgrade-one.sh "$EMB" 'pillow' '$W/tools/embed-venv/bin/python3 -c "import PIL;print(PIL.__version__)"' || true

# 4) 报告
{
  echo "# 依赖升级报告 $(date '+%F %T')";
  echo; echo "## 逐包结果（包|旧|新|结果）"; sed 's/^/- /' "$CSV";
  echo; echo "## 回滚"; echo "回滚命令：venv/bin/pip install -r state/rollback/pkg-20261029/<venv>-freeze.txt";
  echo; echo "## 评审"; echo "评审目录 $LATEST（有效 $OK 份）";
} > "$REP"
bash $W/tools/notify.sh "依赖升级完成：$(grep -c '|OK' "$CSV" 2>/dev/null) 成功 / $(grep -c ROLLED "$CSV" 2>/dev/null) 回滚" || true
echo "=== $(date '+%F %T') 结束 ==="
