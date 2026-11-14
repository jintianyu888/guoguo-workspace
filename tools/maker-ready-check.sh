#!/bin/bash
# maker-ready-check.sh — 重启后确认 3D 打印管家已载入并读设备状态（零 token）
set -u
LOG=/home/j/.openclaw/workspace/state/work/maker-ready.log
OC=/home/j/.npm-global/bin/openclaw
ok=0
for i in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 http://127.0.0.1:18789/healthz 2>/dev/null)
  [ "$code" = "200" ] && { ok=1; break; }
  sleep 10
done
if [ "$ok" != 1 ]; then
  echo "$(date -Is) gateway not healthy" >> $LOG
  bash /home/j/.openclaw/workspace/tools/notify.sh --alert "3D 打印管家就位检查失败：重启后网关未恢复 200" 
  exit 1
fi
listed=$($OC agents list 2>/dev/null | grep -c maker)
st=/home/j/.openclaw/workspace/state/3dprint/state.json
sum='设备状态文件暂缺（监视器未写过）'
if [ -f "$st" ]; then
  sum=$(python3 -c "import json;d=json.load(open('$st'));print('在线' if d.get('connected') else '未连接', '|', d.get('gcode_state') or 'idle', '| 进度', d.get('mc_percent','-'),'%')" 2>/dev/null || echo '状态文件解析失败')
fi
msg="3D打印管家已就位（makers=$( [ "$listed" -gt 0 ] && echo 已注册 || echo 未注册 )）\n$sum"
echo "$(date -Is) $msg" >> $LOG
bash /home/j/.openclaw/workspace/tools/notify.sh "$msg"


systemctl --user stop oc-maker-ready.timer 2>/dev/null || true
