#!/bin/bash
# 每日 NVR 人脸扫描（扫前一天录像，零 token 本地跑）
# v3 2026-10-24：取帧层换成 ISAPI（ContentMgmt search+download），比 RTSP 回放快 ~25 倍；
#   保留 RTSP 为保底开关：NVR_SOURCE=rtsp 走旧脚本。双审必改项：分段、size 过滤、磁盘检查、
#   临时段用完即删、孤儿清扫、单通道灰度可切。
cd /home/j/.openclaw/workspace || exit 1
D=${1:-$(date -d yesterday +%F)}
LOG=state/work/nvr-face-scan.log
PYBIN=/home/j/.openclaw/venvs/face/bin/python
SRC=${NVR_SOURCE:-isapi}

# 单实例锁（2026-10-24 事故修复）：同一 date 被两套实例相隔 80 秒各起一次，
#  共用 _seg/seg.ps 且各自 rm -rf 输出目录 → 互相打断、覆盖率不可信。
LOCKF=state/work/nvr-scan-daily.lock
exec 9>"$LOCKF"
if ! flock -n 9; then
  # 锁龄必须按「持有者进程已运行时长」算，不能用文件 mtime：
  #   exec 9> 是 O_TRUNC，会被挡住的本实例自己把 mtime 刷成当前时刻，算出来永远≈0。
  HPID=$(fuser "$LOCKF" 2>/dev/null | tr -s ' ' '\n' | grep -E '^[0-9]+$' | grep -v "^$$$" | head -1)
  AGE=0
  [ -n "$HPID" ] && AGE=$(ps -o etimes= -p "$HPID" 2>/dev/null | tr -d ' ')
  [ -z "$AGE" ] && AGE=0
  if [ "$AGE" -gt 21600 ]; then
    echo "$(date '+%F %T') WARN 锁被占 ${AGE}s（>6h，疑似僵死），$D 本轮未扫" >> "$LOG"
    NOTIFY_ALERT=1 bash tools/notify.sh "🚨 NVR扫描被锁挡住 ${AGE}s（>6h），疑似僵死实例，$D 未扫" 2>/dev/null || true
  else
    echo "$(date '+%F %T') SKIP 已有实例在跑（$D）锁龄 ${AGE}s，本实例退出" >> "$LOG"
    bash tools/notify.sh "⚠️ NVR人脸扫描($D) 已有实例在跑（锁龄 ${AGE}s），本次跳过" 2>/dev/null || true
  fi
  exit 3
fi

if ! "$PYBIN" -c "import insightface" >/dev/null 2>&1; then
  echo "❌ NVR人脸扫描未执行：venv 缺 insightface 模块（依赖缺失 ≠ 无异常）"
  echo "$(date '+%F %T') PREFLIGHT_FAIL missing=insightface" >> "$LOG"
  exit 2
fi

# ── 静默窗守卫（P3 2026-10-26）──────────────────────────────────────────────
# 路由器 04:00–06:05 定时断网：03:50 起 checkpoint 后 exit 0，06:10 由 cron 重入续跑。
# 断点：state/security/coverage.tsv（date <TAB> ts <TAB> channel <TAB> status <TAB> frames）
COV=state/security/coverage.tsv
mkdir -p state/security
touch "$COV" 2>/dev/null || true
RESUME_DATE=state/work/nvr-resume-date   # 06:10 续跑 cron 读它（修跨日错配）
QUIET_FLAG=state/work/nvr-quiet.flag     # 运行中撞进静默窗的标记（2026-10-28 补）
HM=${NVR_FAKE_HM:-$(date +%H%M)}   # NVR_FAKE_HM 仅供测试守卫
HM10=$((10#$HM))   # 十进制化，避免 0830 这类被当非法八进制
if [ "$HM10" -ge 350 ] && [ "$HM10" -lt 610 ]; then
  echo "$(date '+%F %T') QUIET-WINDOW checkpoint exit0 date=$D hm=$HM" >> "$LOG"
  printf '%s\t%s\t-\tcheckpoint\t0\n' "$D" "$(date '+%F %T')" >> "$COV"
  echo "$D" > "$RESUME_DATE" 2>/dev/null || true
  echo "⏸ NVR人脸扫描($D) 进入静默窗(03:50–06:10)，已 checkpoint，06:10 续跑"
  exit 0
fi
# 已扫通道跳过（06:10 续跑时只补没扫完的）
DONE_CH=$(awk -F'\t' -v d="$D" '$1==d && $4=="ok"{print $3}' "$COV" 2>/dev/null | sort -u | tr '\n' ' ')
[ -n "$DONE_CH" ] && echo "$(date '+%F %T') RESUME 已完成通道: $DONE_CH" >> "$LOG"

if [ -f "$RESUME_DATE" ] && [ "$(cat "$RESUME_DATE" 2>/dev/null)" = "$D" ]; then rm -f "$RESUME_DATE" 2>/dev/null || true; fi

if [ "$SRC" = "rtsp" ]; then
  "$PYBIN" tools/nvr-face-scan.py --date "$D" --channels 101,301,701,1001,1201,1301,1401,1501,1601 --fps 0.1 >> "$LOG" 2>&1
  RC=$?
else
  OUT=state/tmp/nvr_isapi
  mkdir -p "$OUT"
  rm -rf "$OUT"/_seg
  # 本日期若没有已完成通道，清掉该日期的半截产物（只清本日，别的日期不动）
  [ -z "$DONE_CH" ] && rm -rf "$OUT"/ch*_"$D"_* 2>/dev/null
  # 本日期若没有已完成通道，清掉该日期的半截产物（只清本日，别的日期不动）
  [ -z "$DONE_CH" ] && rm -rf "$OUT"/ch*_"$D"_* 2>/dev/null   # 只清临时段；续跑时保留已扫通道产物（P3 2026-10-26）
  scan_ch() {
    local ch=$1
    exec 9>&-   # 子进程不继承锁 fd：父进程被 kill 后锁不会被子进程"假占用"
    case " $DONE_CH " in
      *" $ch "*) echo "$(date '+%F %T') SKIP ch$ch 已扫过($D)" >> "$LOG"; return 0;;
    esac
    python3 tools/nvr-fetch-isapi.py --channel "$ch" --date "$D" --hours 7-23 \
      --fps 0.1 --window 600 --max-frames 80 --out "$OUT" >> "$LOG" 2>&1
    local rc=$?
    for d in "$OUT"/ch${ch}_"$D"_*; do
      [ -d "$d" ] || continue
      sh tools/gpu-run.sh "$PYBIN" tools/face-scan-frames.py "$d" >> "$LOG" 2>&1
    done
    local nf
    nf=$(ls "$OUT"/ch${ch}_"$D"_*/ 2>/dev/null | grep -c '\.jpg$')
    if [ "$rc" -eq 0 ] && [ "${nf:-0}" -gt 0 ]; then
      printf '%s\t%s\t%s\tok\t%s\n' "$D" "$(date '+%F %T')" "$ch" "${nf:-0}" >> "$COV"
    elif [ "$rc" -eq 0 ]; then
      printf '%s\t%s\t%s\tempty\t%s\n' "$D" "$(date '+%F %T')" "$ch" 0 >> "$COV"
    else
      printf '%s\t%s\t%s\tfail\t%s\n' "$D" "$(date '+%F %T')" "$ch" "${nf:-0}" >> "$COV"
    fi
    HMN=$((10#$(date +%H%M)))
    if [ "$HMN" -ge 350 ] && [ "$HMN" -lt 610 ]; then : > "$QUIET_FLAG"; fi
    return $rc
  }
  export -f scan_ch 2>/dev/null || true
  quiet_check() {
    if [ -f "$QUIET_FLAG" ]; then
      rm -f "$QUIET_FLAG"
      echo "$(date '+%F %T') QUIET-WINDOW mid-run checkpoint exit0 date=$D hm=$(date +%H%M)" >> "$LOG"
      printf '%s\t%s\t-\tcheckpoint\t0\n' "$D" "$(date '+%F %T')" >> "$COV"
      echo "$D" > "$RESUME_DATE" 2>/dev/null || true
      echo "⏸ 运行中撞进静默窗，已 checkpoint，06:10 续跑"
      exit 0
    fi
  }
  scan_ch 101 & scan_ch 301 & scan_ch 701 &
  wait
  quiet_check
  scan_ch 1001 & scan_ch 1201 & scan_ch 1301 &
  wait
  quiet_check
  scan_ch 1401 & scan_ch 1501 & scan_ch 1601 &
  wait
  quiet_check
  RC=0
  for ch in 101 301 701 1001 1201 1301 1401 1501 1601; do
    n=$(ls "$OUT"/ch${ch}_"$D"_*/ 2>/dev/null | grep -c '\.jpg$')
    [ "${n:-0}" -eq 0 ] && echo "$(date '+%F %T') WARN ch$ch 0 帧" >> "$LOG"
  done
  rm -rf "$OUT"/_seg
fi

# ── 留存策略（2026-11-02 加，双审：minimax 条件通过 / qianwen 通过）──────
# state/tmp/nvr_isapi 是派生缓存（上游 NVR 仍存原始录像，可再生），按天保留
# N 天后硬删并记账。不走回收站：搬过去等于没腾出空间。默认 7 天。
RETENTION_DAYS=${NVR_RETENTION_DAYS:-7}
CUTOFF=$(date -d "-$((RETENTION_DAYS-1)) days" +%F 2>/dev/null) || CUTOFF=""
purge_old() {
  [ -n "$CUTOFF" ] || { echo "$(date '+%F %T') RETENTION SKIP 无法计算截止日期" >> "$LOG"; return 0; }
  local n=0 s=0 d b dd sz fail=0
  shopt -s nullglob
  for d in "$OUT"/ch*_*; do
    [ -d "$d" ] || continue
    b=$(basename "$d")
    # 严格校验目录名：ch<数字>_YYYY-MM-DD_HH，不合规一律跳过
    [[ "$b" =~ ^ch[0-9]+_([0-9]{4}-[0-9]{2}-[0-9]{2})_[0-9]{2}$ ]] || continue
    dd="${BASH_REMATCH[1]}"
    [ "$dd" = "$D" ] && continue            # 绝不碰本轮正在处理的日期
    [ "$dd" \< "$CUTOFF" ] || continue       # 保留窗口内不动
    sz=$(du -sk "$d" 2>/dev/null | cut -f1); sz=${sz:-0}
    if rm -rf "$d" 2>/dev/null; then
      n=$((n+1)); s=$((s+sz))
      printf '{"ts":"%s","dir":"%s","kb":%s,"keep_from":"%s"}\n' \
        "$(date '+%F %T')" "$b" "$sz" "$CUTOFF" >> state/work/nvr-retention-ledger.jsonl
    else
      fail=$((fail+1)); echo "$(date '+%F %T') RETENTION FAIL 删除失败 $b" >> "$LOG"
    fi
  done
  shopt -u nullglob
  [ "$n" -gt 0 ] && echo "$(date '+%F %T') RETENTION 清理 $n 个目录 释放 $((s/1024))MB keep>=${CUTOFF}" >> "$LOG"
  if [ "$fail" -gt 0 ]; then
    NOTIFY_ALERT=1 bash tools/notify.sh "⚠️ NVR留存清理有 ${fail} 个目录删除失败（详见 NVR 扫描日志）" 2>/dev/null || true
  fi
  return 0
}
purge_old

if [ "${RC:-0}" -ne 0 ]; then
  echo "❌ NVR人脸扫描($D)失败 rc=$RC（详见 $LOG 最后30行）："
  tail -30 "$LOG"
  exit $RC
fi
echo "🎬 NVR人脸扫描($D)完成 src=$SRC rc=0 · 人脸库共 $(ls state/faces/collected 2>/dev/null | wc -l) 张"
