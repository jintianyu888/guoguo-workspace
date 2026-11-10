#!/usr/bin/env python3
'''hf-dl.py — 用 HF 镜像批量拉整仓库（默认 hf-mirror）'''
import os, sys, time
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
from huggingface_hub import snapshot_download

def main():
    if len(sys.argv) < 2:
        print('用法: hf-dl.py <repo> [repo...]'); return 2
    rc = 0
    for repo in sys.argv[1:]:
        t0 = time.time()
        print(f'== {repo} 开始 {time.strftime("%H:%M:%S")}', flush=True)
        try:
            p = snapshot_download(repo_id=repo, resume_download=True, max_workers=4,
                                 local_dir=None)
            sz = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(p)
                     for f in fs if os.path.isfile(os.path.join(d, f)) and not os.path.islink(os.path.join(d, f)))
            print(f'== {repo} 完成 用时 {time.time()-t0:.0f}s 实占 {sz/1e9:.2f}GB 路径 {p}', flush=True)
        except Exception as e:
            rc = 1
            print(f'== {repo} 失败: {type(e).__name__}: {e}', flush=True)
    return rc

if __name__ == '__main__':
    sys.exit(main())
