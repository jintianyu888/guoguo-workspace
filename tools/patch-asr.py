import re
p = "/home/j/.openclaw/workspace/tools/asr"
s = open(p).read()
if "LD_LIBRARY_PATH" in s:
    print("already patched")
else:
    old = 'DIR="$(cd "$(dirname "$0")" && pwd)"'
    new = ('DIR="$(cd "$(dirname "$0")" && pwd)"\n'
           '# 2026-09-28 加：venv 里的 CUDA 库（cuBLAS/nvrtc）挂进库路径，ASR 才走得动 GPU\n'
           'for d in "$DIR"/asr-venv/lib/python*/site-packages/nvidia/*/lib; do\n'
           '  [ -d "$d" ] && LD_LIBRARY_PATH="$d${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n'
           'done\n'
           'export LD_LIBRARY_PATH')
    if old in s:
        s = s.replace(old, new, 1)
        open(p, "w").write(s)
        print("patched OK")
    else:
        print("anchor not found")