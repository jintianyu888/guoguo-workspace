#!/usr/bin/env python3
"""hw-bench-compare.py A.json B.json — 对比两次基准，输出变化率表"""
import json,sys
a=json.load(open(sys.argv[1])); b=json.load(open(sys.argv[2]))
def g(d,path):
    cur=d
    for k in path.split('.'):
        if not isinstance(cur,dict) or k not in cur: return None
        cur=cur[k]
    return cur
KEYS=[("cpu.single_ops_per_s","ops/s"),("cpu.multi_ops_per_s","ops/s"),("cpu.multi_scaling","x"),
      ("mem.copy_256mb_gbps","GB/s"),("mem.copy_1024mb_gbps","GB/s"),("mem.scale_mb_per_s","MB/s"),
      ("gpu.fp16_tflops","TFLOPS"),("gpu.fp32_tflops","TFLOPS"),
      ("disk.ext4_seq_write_mbs","MB/s"),("disk.ext4_seq_read_mbs","MB/s"),("disk.ninep_seq_write_mbs","MB/s")]
print("基准A: %s (%s)   基准B: %s (%s)" % (a.get("stamp"),a.get("tag"),b.get("stamp"),b.get("tag")))
print("%-30s %>0s" % ("指标",""))
print("%-30s %12s %12s %10s  %s" % ("指标","A","B","变化","单位"))
for k,u in KEYS:
    va,vb=g(a,k),g(b,k)
    if not isinstance(va,(int,float)) or not isinstance(vb,(int,float)): continue
    d=(vb-va)/va*100 if va else 0
    print("%-30s %12.2f %12.2f %9.1f%%  %s" % (k,va,vb,d,u))
oa=g(a,"ollama") or {}; ob=g(b,"ollama") or {}
for m in sorted(set(oa)|set(ob)):
    x=(oa.get(m) or {}).get("gen_tok_s"); y=(ob.get(m) or {}).get("gen_tok_s")
    if isinstance(x,(int,float)) and isinstance(y,(int,float)):
        print("ollama %-24s %12.2f %12.2f %9.1f%%  tok/s" % (m[:24],x,y,(y-x)/x*100 if x else 0))
