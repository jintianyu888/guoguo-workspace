#!/usr/bin/env bash
# cleanup-root.sh — A 机软件卸载（需 root）。2026-11-10 由果果生成，逐条可回滚。
# 用法：
#   sudo bash tools/cleanup-root.sh --dry      # 只看会做什么
#   sudo bash tools/cleanup-root.sh --apt      # 只清 apt 无用件（cmake）
#   sudo bash tools/cleanup-root.sh --sec      # 卸载 clamav + rkhunter + debsecan（省 1G 内存）
#   sudo bash tools/cleanup-root.sh --apt --sec
set -u
MODE_APT=0; MODE_SEC=0; DRY=0
for a in "$@"; do
  case "$a" in
    --apt) MODE_APT=1;;
    --sec) MODE_SEC=1;;
    --dry) DRY=1;;
    *) echo "未知参数 $a"; exit 2;;
  esac
done
if [ $DRY -eq 0 ]; then [ $EUID -eq 0 ] || { echo "必须用 sudo 运行（只预览可加 --dry）"; exit 4; }; fi
say() { echo "[cleanup] $*"; }
doit() { if [ $DRY -eq 1 ]; then say "DRY: $*"; else eval "$@"; fi; }

if [ $MODE_APT -eq 1 ]; then
  say "== apt 侧：只动 cmake（43MB，编译工具，当前无编译需求；需要时 apt install cmake 一条命令装回） =="
  doit "apt-get -y --purge autoremove cmake"
  say "保留说明：cifs-utils(NAS挂载)、poppler-utils/imagemagick/img2pdf(打印链路)、ubuntu-minimal/ubuntu-wsl/apt-transport-https(元包) 一律不动"
fi

if [ $MODE_SEC -eq 1 ]; then
  say "== 安全扫描：clamav-daemon(常驻 989MB 内存 + 171MB 病毒库) / rkhunter / debsecan =="
  doit "systemctl stop clamav-daemon clamav-freshclam 2>/dev/null || true"
  doit "apt-get -y --purge remove clamav-daemon clamav-freshclam clamav-base clamav-freshclam-ifupdown 2>/dev/null || true"
  doit "apt-get -y --purge remove rkhunter debsecan"
  doit "rm -f /etc/cron.d/debsecan /etc/cron.daily/rkhunter /etc/cron.weekly/rkhunter"
  doit "rm -rf /var/lib/clamav"
  say "回滚：apt-get install -y clamav-daemon clamav-freshclam rkhunter debsecan && systemctl enable --now clamav-daemon"
fi

say "== 收尾 =="
doit "apt-get -y autoremove --purge"
doit "apt-get clean"
say "完成。回滚点：/var/log/apt/history.log 里本次会话的 Remove 行可用 apt-get install 反向装回"
