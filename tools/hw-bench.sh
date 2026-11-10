#!/usr/bin/env bash
# hw-bench.sh v1.0 — 本机硬件基准（换硬件前后对比用）
# 用法:
#   bash tools/hw-bench.sh baseline          # 存 state/bench/bench-<时间>-baseline.json
#   bash tools/hw-bench.sh after --ollama    # 含 ollama 吞吐（注意：ollama 在局域网另一台机上）
#   bash tools/hw-bench.sh --compare A.json B.json
set -uo pipefail
ROOT="/home/j/.openclaw/workspace"
OUTDIR="$ROOT/state/bench"
mkdir -p "$OUTDIR"
PY="/home/j/.openclaw/venvs/tts312/bin/python"
[ -x "$PY" ] || PY=python3
TAG="run"; DO_OLLAMA=0
for a in "$@"; do if [ "$a" = "--ollama" ]; then DO_OLLAMA=1; elif [ "$a" != "--compare" ]; then TAG="$a"; fi; done
if [ "${1:-}" = "--compare" ]; then exec "$PY" "$ROOT/tools/hw-bench-compare.py" "$2" "$3"; fi
STAMP=$(date +%Y%m%d-%H%M%S)
JSON="$OUTDIR/bench-$STAMP-$TAG.json"
echo "== hw-bench $TAG @ $STAMP =="
DO_OLLAMA=$DO_OLLAMA STAMP=$STAMP TAG=$TAG JSON=$JSON HOME_DIR="$HOME" "$PY" - <<'PYEOF'
import json,os,subprocess,sys,time

out_path=os.environ["JSON"]; stamp=os.environ["STAMP"]; tag=os.environ["TAG"]
do_ollama=os.environ.get("DO_OLLAMA","0")=="1"
H={}; R={}

def run(cmd,timeout=600):
    try:
        return subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=timeout).stdout
    except Exception:
        return ""

def csv_lines(text):
    out=[]
    for ln in text.replace("\r","").splitlines():
        ln=ln.strip()
        if not ln or ln.startswith('"DeviceLocator"') or ln.startswith('"Name"'): continue
        out.append(ln.strip('"'))
    return out

H["wsl_cpu"]=run("lscpu | grep -m1 'Model name' | cut -d: -f2-").strip()
H["wsl_threads"]=os.cpu_count()
try:
    H["wsl_mem_gb"]=round(int([l for l in open('/proc/meminfo') if l.startswith('MemTotal')][0].split()[1])/1048576,1)
except Exception: pass
ps="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
PSC=ps+" -NoProfile -Command "
H["win_cpu"]=csv_lines(run(PSC+'"Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Csv -NoTypeInformation"'))
H["win_ram"]=csv_lines(run(PSC+'"Get-CimInstance Win32_PhysicalMemory | Select-Object DeviceLocator,Capacity,ConfiguredClockSpeed | ConvertTo-Csv -NoTypeInformation"'))
H["win_gpu"]=csv_lines(run(PSC+'"Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion | ConvertTo-Csv -NoTypeInformation"'))
nvs="/usr/lib/wsl/lib/nvidia-smi"
if not os.path.exists(nvs): nvs="nvidia-smi"
H["nvidia"]=run(nvs+" --query-gpu=name,memory.total,driver_version --format=csv,noheader").strip()

def sps(n):
    t=time.perf_counter(); x=0
    for _ in range(n): x=(x*1103515245+12345)&0xFFFFFFFF
    return n/(time.perf_counter()-t)

sps(200000)
R["cpu"]={"single_ops_per_s":round(sps(3000000))}
nt=os.cpu_count() or 4
OPS=1500000
code=("import time\nx=0\nt=time.perf_counter()\n"
      "for _ in range(OPSN): x=(x*1103515245+12345)&0xFFFFFFFF\n"
      "print(OPSN/(time.perf_counter()-t))").replace("OPSN",str(OPS))
vals=[]
try:
    ps=[subprocess.Popen([sys.executable,"-c",code],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True) for _ in range(nt)]
    vals=[float(p.communicate()[0].strip()) for p in ps]
except Exception as e:
    R["cpu"]["multi_error"]=str(e)[:120]
R["cpu"]["multi_threads"]=nt
if vals:
    R["cpu"]["multi_ops_per_s"]=round(sum(vals))
    R["cpu"]["multi_scaling"]=round(sum(vals)/max(R["cpu"]["single_ops_per_s"],1),2)
else:
    R["cpu"]["multi_ops_per_s"]=None; R["cpu"]["multi_scaling"]=None

R["mem"]={}
try:
    import numpy as np
    for mb in (256,1024):
        a=np.ones(mb*131072,dtype=np.float32); b=np.empty_like(a)
        for _ in range(3): np.copyto(b,a)
        t=time.perf_counter()
        for _ in range(8): np.copyto(b,a)
        dt=time.perf_counter()-t
        R["mem"]["copy_"+str(mb)+"mb_gbps"]=round((a.nbytes*2*8/dt)/1e9,1)
    R["mem"]["scale_mb_per_s"]=round(R["mem"]["copy_1024mb_gbps"]*953.7)
except Exception as e:
    R["mem"]["error"]=str(e)[:140]

try:
    import torch
    if torch.cuda.is_available():
        dev="cuda"
        def mm(dt,size=6144,iters=16):
            a=torch.randn(size,size,device=dev,dtype=dt); b=torch.randn(size,size,device=dev,dtype=dt)
            for _ in range(3): c=a@b
            torch.cuda.synchronize(); t=time.perf_counter()
            for _ in range(iters): c=a@b
            torch.cuda.synchronize(); el=time.perf_counter()-t
            return round((2*size**3*iters)/el/1e12,2)
        g={"name":torch.cuda.get_device_name(0),"torch":torch.__version__,"cuda":torch.version.cuda,
           "vram_gb":round(torch.cuda.get_device_properties(0).total_memory/1e9,1)}
        g["fp16_tflops"]=mm(torch.float16); g["fp32_tflops"]=mm(torch.float32)
        try: g["bf16_tflops"]=mm(torch.bfloat16)
        except Exception: pass
        R["gpu"]=g
    else:
        R["gpu"]={"error":"cuda unavailable"}
except Exception as e:
    R["gpu"]={"error":str(e)[:160]}

def dd_test(path,mb):
    os.makedirs(path,exist_ok=True)
    f=os.path.join(path,".hwbench-"+str(os.getpid())+".tmp")
    try:
        chunk=b"\0"*(1024*1024)
        t=time.perf_counter()
        with open(f,"wb") as fh:
            for _ in range(mb): fh.write(chunk)
            fh.flush(); os.fsync(fh.fileno())
        w=round(mb/(time.perf_counter()-t),1)
        t=time.perf_counter()
        with open(f,"rb") as fh:
            while fh.read(4*1024*1024): pass
        r=round(os.path.getsize(f)/1048576/(time.perf_counter()-t),1)
        return w,r
    except Exception:
        return None,None
    finally:
        try: os.remove(f)
        except Exception: pass

R["disk"]={}
for label,path,mb in (("ext4","/tmp",1024),("ninep","/mnt/e/openclaw-store",256)):
    w,r=dd_test(path,mb)
    if w is not None:
        R["disk"][label+"_seq_write_mbs"]=w; R["disk"][label+"_seq_read_mbs"]=r

R["ollama"]={}
if do_ollama:
    import urllib.request
    def gen(model,np_=96):
        body=json.dumps({"model":model,"prompt":"用一句话解释内存带宽对本地大模型推理速度的影响。","stream":False,
                         "options":{"num_predict":np_,"temperature":0}}).encode()
        req=urllib.request.Request("http://127.0.0.1:11434/api/generate",data=body,headers={"Content-Type":"application/json"})
        t=time.perf_counter()
        with urllib.request.urlopen(req,timeout=1200) as resp: d=json.loads(resp.read())
        wall=round(time.perf_counter()-t,1)
        ec=d.get("eval_count") or 0; ed=d.get("eval_duration") or 1
        pc=d.get("prompt_eval_count") or 0; pd=d.get("prompt_eval_duration") or 1
        return {"total_s":wall,"gen_tok_s":round(ec/(ed/1e9),2) if ec else None,
                "prefill_tok_s":round(pc/(pd/1e9),1) if pc else None,
                "load_s":round((d.get("load_duration") or 0)/1e9,1),"gen_tokens":ec}
    for m in ("qwen3:14b","qwen3:30b-a3b-instruct-2507-q4_K_M","gpt-oss:20b"):
        try: R["ollama"][m]=gen(m)
        except Exception as e: R["ollama"][m]={"error":str(e)[:110]}

os.makedirs(os.path.dirname(out_path),exist_ok=True)
tmp=out_path+".tmp"
json.dump({"stamp":stamp,"tag":tag,"host":H,"results":R},open(tmp,"w"),ensure_ascii=False,indent=2)
os.replace(tmp,out_path)

print("CPU     : "+str(H.get("wsl_cpu"))+" / "+str(H.get("wsl_threads"))+" 线程")
print("Windows : "+str(H.get("win_cpu"))+" | RAM "+str(H.get("win_ram"))+" | GPU "+str(H.get("win_gpu")))
print("CPU 单线程 ops/s : {:,}".format(R["cpu"]["single_ops_per_s"]))
print("CPU 多线程 ops/s : {:,}  缩放 {}x / {} 线程".format(R["cpu"]["multi_ops_per_s"],R["cpu"]["multi_scaling"],R["cpu"]["multi_threads"]))
print("内存带宽 GB/s    : "+str(R["mem"].get("copy_1024mb_gbps","n/a"))+"  (copy 1GB)")
print("GPU              : "+json.dumps(R.get("gpu",{}),ensure_ascii=False)[:220])
print("磁盘             : "+json.dumps(R["disk"],ensure_ascii=False))
if R["ollama"]: print("ollama           : "+json.dumps(R["ollama"],ensure_ascii=False)[:600])
print("写入: "+out_path)
PYEOF