#!/bin/sh
# footer-host.sh —— 页脚机器状态（零 token；纯读 /proc 与 WSL 的 nvidia-smi）
# 2026-10-27 修两处假数据（主公反馈"CPU/GPU 与 Windows 性能窗口对不上"）：
#   1) PID 原用 pgrep -f openclaw 抓到别的进程 → VmRSS 读不到 → 内存恒显示 0.0GB
#      改为 systemd MainPID，失败再退到精确匹配网关主进程
#   2) 原只给 load（1 分钟均值），与任务管理器 CPU% 不可比 → 新增 /proc/stat 差分实时 CPU%
GW=$(systemctl --user show openclaw-gateway -p MainPID --value 2>/dev/null | tr -d '\r')
case "$GW" in ''|0) GW=$(pgrep -f 'openclaw/dist/index.js gateway' | head -n 1) ;; esac

cpu_pct() {
  set -- $(awk '/^cpu /{t=0; for(i=2;i<=NF;i++) t+=$i; printf "%s %s", t, $5+$6}' /proc/stat)
  t1=$1; i1=$2
  sleep 0.4
  set -- $(awk '/^cpu /{t=0; for(i=2;i<=NF;i++) t+=$i; printf "%s %s", t, $5+$6}' /proc/stat)
  t2=$1; i2=$2
  awk -v a="$t1" -v b="$i1" -v c="$t2" -v d="$i2" 'BEGIN{x=c-a; if(x<=0){print "n/a"; exit} printf "%.0f%%", (1-(d-b)/x)*100}'
}

load=$(cut -d" " -f1 /proc/loadavg)
tot=$(awk "/MemTotal/{print \$2}" /proc/meminfo)
av=$(awk "/MemAvailable/{print \$2}" /proc/meminfo)
mem=$(awk -v t="$tot" -v a="$av" "BEGIN{printf \"%.0f%%(%.1f/%.1fGB)\",(t-a)*100/t,(t-a)/1048576,t/1048576}")
disk=$(df -h / | awk "NR==2{print \$5}")
cpu=$(cpu_pct)
echo "🖥 主机：CPU $cpu · 负载 $load / $(nproc) 线程 · 内存 $mem · 磁盘 $disk"

if [ -n "$GW" ] && [ -r "/proc/$GW/status" ]; then
  rsskb=$(awk "/VmRSS/{print \$2}" /proc/$GW/status)
  awk -v k="$rsskb" -v pid="$GW" 'BEGIN{printf "🧠 网关(PID %s)：内存 %.2fGB（占软限 %.0f%%）\n", pid, k/1048576, k/1048576/9*100}'
else
  echo "🧠 网关：进程未找到"
fi

NVS=/usr/lib/wsl/lib/nvidia-smi
[ -x "$NVS" ] || NVS=$(command -v nvidia-smi 2>/dev/null)
if [ -n "$NVS" ] && [ -x "$NVS" ]; then
  timeout 6 "$NVS" --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader 2>/dev/null \
    | awk -F', ' '{printf "🎮 GPU：%s · 占用 %s · 显存 %s/%s · %s°C\n",$1,$2,$3,$4,$5}'
else
  echo "🎮 GPU：nvidia-smi 不可用"
fi
