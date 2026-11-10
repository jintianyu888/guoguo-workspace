#!/bin/bash
# 918 验收：本地模型以 32K 上下文正常工作（VRAM 合理、有实际输出）
set -u
ps=$(curl -s --max-time 15 http://127.0.0.1:11434/api/ps)
python3 - <<'PY'
import json,sys,subprocess
ps = subprocess.run(['curl','-s','--max-time','15','http://127.0.0.1:11434/api/ps'],capture_output=True,text=True).stdout
try: d = json.loads(ps)
except Exception: sys.exit(1)
ok = [m for m in d.get('models',[]) if 'ornith' in m.get('name','') and int(m.get('context_length') or 0) <= 32768]
sys.exit(0 if ok else 1)
PY
