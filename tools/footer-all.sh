#!/bin/sh
# footer-all.sh v5 —— 页脚单一来源（14 项固定 + 自检）；主机/网关/GPU/下载全部内联自测，缺项占位
W=/home/j/.openclaw/workspace
TS="${1:-}"
T=$(mktemp)
# 2026-10-24 修：在网关内部直调 openclaw status 会卡死整条管道（页脚输出 0 字节），加 timeout 兜底
ST=$(timeout 20 openclaw status 2>/dev/null || true)
# 2026-10-24 修（双审 GO-WITH-FIXES）：原来写死 'agent:main:main'，抓到的是另一条会话（heartbeat），
# 而本会话在 status 表里被列宽截断成 'agent:main:feishu:di' —— 页脚与监控面板长期不同源。
# 现改为：用完整 session key（FOOTER_SKEY）精确识别；status 行仅按「截断值=完整key前缀且唯一」匹配；
# 取不到再退 panel /api/state 精确匹配 totalTokens（此时缓存标未采集，不编造）。绝不回退 agent:main:main。
SKEY=${FOOTER_SKEY:-agent:main:feishu:direct:ou_74fec7bc81cc6ec6d2b4de1c0967923b}
TOK=$(printf '%s\n' "$ST" | SKEY="$SKEY" python3 $W/tools/footer-row.py status 2>/dev/null)
if [ -z "$TOK" ]; then
  _API=$(curl -s --max-time 4 http://127.0.0.1:8899/api/state 2>/dev/null)
  [ -n "$_API" ] && TOK=$(printf '%s' "$_API" | SKEY="$SKEY" python3 $W/tools/footer-row.py api 2>/dev/null)
fi
RAY=0
if [ -n "$TOK" ]; then
  DOM=$(printf '%s' "$TOK" | grep -oE '[0-9]+k/1\.0m \([0-9]+%\)' | head -n 1)
  if [ -z "$DOM" ]; then
    # 兜底模式或格式变了：若与 panel 精确值可对上则 RAW=1，否则视为未采集
    _P=$(printf '%s' "$_API" | SKEY="$SKEY" python3 $W/tools/footer-row.py api 2>/dev/null)
    [ -n "$_P" ] && RAY=1
  fi
fi
CTX="$DOM"
[ -n "$CTX" ] || CTX=$(printf '%s' "$TOK" | head -n 1)
# 上下文阈值提醒（2026-10-02 主公令·新会话优化）：≥70% ⚠️ 建议开新会话；≥85% 🔴 请开新会话
CTXP=$(echo "$CTX" | grep -oE '\(([0-9]+)%\)' | tr -dc '0-9')
CTXH=""
[ -n "$CTXP" ] && [ "$CTXP" -ge 70 ] && CTXH=" ⚠️ 偏高·建议开新会话"
[ -n "$CTXP" ] && [ "$CTXP" -ge 85 ] && CTXH=" 🔴 已满·请开新会话"
PEAK=$(sh $W/tools/host-peak-report.sh 2>/dev/null | grep -E 'CPU 负载峰值|内存峰值' | tr '\n' ' ' | cut -c1-100)
# 2026-10-24 修：peak-status 第 1 行才是「当前时段」结论，第 2 行是建议；原来取 tail 导致时段栏只剩建议
TIME=$(sh $W/tools/peak-status.sh 2>/dev/null | head -n 1 | cut -c1-110)
EL=$([ -n "$TS" ] && sh $W/tools/elapsed.sh "$TS" 2>/dev/null | head -n 1)
LOAD=$(cut -d' ' -f1 /proc/loadavg)
# 近 1 小时平均负载（来自 self-monitor 5 分钟采样），避免拿瞬时尖峰当常态
H1=$(python3 - <<'PY' 2>/dev/null
import re,datetime,statistics
p="/home/j/.openclaw/workspace/state/self-monitor/history.log"
cut=datetime.datetime.now()-datetime.timedelta(minutes=60)
v=[]
try:
    for line in open(p,encoding="utf-8",errors="ignore"):
        m=re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?load=([\d.]+)",line)
        if not m: continue
        try: t=datetime.datetime.strptime(m.group(1),"%Y-%m-%d %H:%M:%S")
        except Exception: continue
        if t>=cut: v.append(float(m.group(2)))
    print("%.2f" % statistics.mean(v) if v else "")
except Exception:
    print("")
PY
)
MEM=$(awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{printf "%.0f%% (%.1f/%.1fGB)", (t-a)*100/t, (t-a)/1048576, t/1048576}' /proc/meminfo)
DISK=$(df -h / | awk 'NR==2{print $5}')
TMPU=$(df -h /tmp | awk 'NR==2{print $5}')
# 2026-10-27 新增：实时 CPU%（/proc/stat 差分 0.4s），与 Windows 任务管理器可比
CPUP=$(set -- $(awk '/^cpu /{t=0; for(i=2;i<=NF;i++) t+=$i; printf "%s %s", t, $5+$6}' /proc/stat); t1=$1; i1=$2; sleep 0.4; set -- $(awk '/^cpu /{t=0; for(i=2;i<=NF;i++) t+=$i; printf "%s %s", t, $5+$6}' /proc/stat); awk -v a=$t1 -v b=$i1 -v c=$1 -v d=$2 'BEGIN{x=c-a; if(x<=0){print "n/a"; exit} printf "%.0f%%",(1-(d-b)/x)*100}')
# 2026-10-27 修：pgrep 会抓到非网关进程（PID/RSS 全错）；改 systemd MainPID
GW=$(systemctl --user show openclaw-gateway -p MainPID --value 2>/dev/null | tr -d '\r')
case "$GW" in ''|0) GW=$(pgrep -f 'openclaw/dist/index.js gateway' | head -n 1) ;; esac
GWR=$([ -n "$GW" ] && awk '/VmRSS/{printf "%.1fGB", $2/1048576}' /proc/$GW/status 2>/dev/null)
NVS="/usr/lib/wsl/lib/nvidia-smi"; [ -x "$NVS" ] || NVS=$(command -v nvidia-smi 2>/dev/null)
GPU=$(timeout 8 "$NVS" --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null | head -n 1)
DLSZ=$(du -shc $W/state/dl/*.part $W/state/dl/*.tmp 2>/dev/null | tail -n 1 | cut -f1)
DLN=$(ls $W/state/dl/*.part $W/state/dl/*.tmp 2>/dev/null | wc -l)
PRC=$(pgrep -cf multi-dl 2>/dev/null || echo 0)
{
  echo "📅 此刻：$(date '+%F %H:%M')　🤖 模型：deepseek/deepseek-flash"
  echo "💰 余额：$(sh $W/tools/ds-balance.sh 2>/dev/null | head -n 1 | tr -d '\r')"
  echo "🧮 用量：${TOK:-未采集}"
  echo "📚 上下文：${CTX:-未采集}${CTXH}"
  echo "💵 花费：见内置页脚（网关自动附加）"
  echo "🗄️ 缓存：$(printf '%s' "$TOK" | grep -oE '[0-9]+% cached' | head -n 1)"
  echo "🕒 时段：${TIME:-暂不可用}"
  echo "📈 主机峰值（今日）：${PEAK:-暂不可用}"
  LBL="$LOAD"; [ -n "${H1:-}" ] && LBL="$LOAD（近1h均 $H1）"
  echo "🖥 主机：CPU ${CPUP:-n/a} · 负载 $LBL / 16 线程 · 内存 $MEM · 磁盘 $DISK · /tmp $TMPU"
  GWPCT=$(awk -v g="$GWR" 'BEGIN{if(g=="")print ""; else printf "（占软限 %.0f%%）", g/9*100}')
  echo "🧠 网关(PID ${GW:-无})：${GWR:-暂不可用}$GWPCT"
  echo "🎮 GPU：${GPU:-暂不可用}"
  echo "⬇️ 下载：进行中 ${DLSZ:-0}（$DLN 个文件）· 进程 $PRC 个 · 已完成的包不占用计数"
  python3 $W/tools/work-status.py 2>/dev/null | head -n 2
  sh $W/tools/footer-tasks.sh 2>/dev/null | head -n 20
  echo "⏱ 本条耗时：${EL:---}"
} > "$T" 2>/dev/null
cat "$T"
fx=0
for k in '📅 此刻' '🤖 模型' '💰 余额' '🧮 用量' '📚 上下文' '💵 花费' '🗄️ 缓存' '🕒 时段' '📈 主机峰值' '🖥 主机' '🧠 网关' '🎮 GPU' '⬇️ 下载' '⏱ 本条耗时'; do grep -q "$k" "$T" && fx=$((fx+1)); done
vx=0
for k in '果果状态' '📋 待办' '🔄 在办' '✅ 今日完成' '⏸ 高峰暂停'; do grep -q "$k" "$T" && vx=$((vx+1)); done
echo "🔢 自检：固定项 $fx/14 · 变量项 $vx/5"
rm -f "$T"# owner 在场计时（供 owner-mode.sh 判定）
mkdir -p /home/j/.openclaw/workspace/state/work && touch /home/j/.openclaw/workspace/state/work/owner-last-seen 2>/dev/null
