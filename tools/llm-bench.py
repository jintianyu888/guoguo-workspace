#!/usr/bin/env python3
# 本地大模型 CPU 推理基准（2026-10-29）
import time, sys, os
from llama_cpp import Llama

MODEL = "/home/j/.openclaw/models/gguf/qwen3-30b-a3b-q4km.gguf"
THREADS = int(os.environ.get("BENCH_THREADS", "16"))
NCTX = int(os.environ.get("BENCH_CTX", "4096"))

t0 = time.time()
llm = Llama(model_path=MODEL, n_ctx=NCTX, n_threads=THREADS, n_gpu_layers=0, verbose=False)
load_s = time.time() - t0
print(f"加载耗时: {load_s:.1f}s  线程: {THREADS}  上下文: {NCTX}", flush=True)

prompt = "请用中文列出三条家庭备份的最佳实践，每条不超过20字。"
t1 = time.time()
out = llm(prompt, max_tokens=200, temperature=0.6, top_p=0.9)
gen_s = time.time() - t1
usage = out["usage"]
n_out = usage["completion_tokens"]
print(f"生成: {n_out} tokens / {gen_s:.1f}s = {n_out/gen_s:.1f} tok/s", flush=True)
print("回复:", out["choices"][0]["text"][:300].replace("\n", " "), flush=True)
