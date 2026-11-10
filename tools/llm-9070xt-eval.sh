#!/bin/bash
# 9070XT(192.168.1.107 ollama) 本地大模型评测 —— 网关托管
OUT=/home/j/.openclaw/workspace/state/bench/9070xt-eval.md
mkdir -p "$(dirname "$OUT")"
M="qwen3:30b-a3b-instruct-2507-q4_K_M"
{
echo "# 9070XT 本地大模型评测 ($(date '+%F %T'))"
echo
echo "## 服务信息"
curl -s -m 8 http://192.168.1.107:11434/api/version
echo; curl -s -m 10 http://192.168.1.107:11434/api/ps
echo
echo "## 生成速度 (qwen3:30b-a3b, 两轮=冷+热)"
for i in 1 2; do
  R=$(curl -s -m 180 http://192.168.1.107:11434/api/generate -d "{\"model\":\"$M\",\"prompt\":\"用一句话介绍你自己\",\"stream\":false}")
  echo "$R" | python3 -c "import sys,json
try:
 d=json.load(sys.stdin)
 print('第%s轮: load=%.1fs total=%.1fs tokens=%s eval=%.2fs -> %.1f tok/s'%(sys.argv[1], d.get('load_duration',0)/1e9, d.get('total_duration',0)/1e9, d.get('eval_count'), d.get('eval_duration',1)/1e9, d.get('eval_count',0)/max(d.get('eval_duration',1)/1e9,1e-9)))
 print('  输出:', (d.get('response') or '')[:60].replace(chr(10),' '))
except Exception as e: print('parse err', e)" $i
done
echo
echo "## 6 题能力快测"
cd /home/j/.openclaw/workspace
python3 -u tools/model-bench/bench.py --tag 9070xt --models-file /home/j/.openclaw/workspace/state/tmp/local-models.txt --repeat 1 --workers 1 --only instr1,code1,json1,math1,reason1,tool1
python3 tools/model-bench/score.py --tag 9070xt
} > "$OUT" 2>&1
echo "DONE -> $OUT"
cat "$OUT"
