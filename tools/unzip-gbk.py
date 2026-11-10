import zipfile, os, shutil
z='/home/j/.openclaw/media/inbound/聊天记录_20261003_145910---df39e8eb-5ab8-4850-b3ca-dd045f1b2aa0.zip'
d='/home/j/.openclaw/workspace-print/print/jobs/unzip-20261003'
shutil.rmtree(d, ignore_errors=True); os.makedirs(d, exist_ok=True)
with zipfile.ZipFile(z) as zf:
    for i in zf.infolist():
        if i.is_dir(): continue
        n=i.filename
        if not (i.flag_bits & 0x800):
            try: n=n.encode('cp437').decode('gbk')
            except Exception: pass
        p=os.path.join(d, n)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with zf.open(i) as s, open(p,'wb') as t: shutil.copyfileobj(s,t)
print('== 修正后的落盘清单（字节 / 路径）==')
for root,_,fs in os.walk(d):
    for f in sorted(fs):
        p=os.path.join(root,f); print(f'{os.path.getsize(p)}\t{p}')