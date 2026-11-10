import zipfile, os
z='/home/j/.openclaw/media/inbound/聊天记录_20261003_145910---df39e8eb-5ab8-4850-b3ca-dd045f1b2aa0.zip'
d='/home/j/.openclaw/workspace-print/print/jobs/unzip-20261003'
os.makedirs(d, exist_ok=True)
with zipfile.ZipFile(z) as zf:
    zf.extractall(d)
    print('== ZIP 内条目（原始字节 / 名称）==')
    for i in zf.infolist():
        print(f'{i.file_size}\t{i.filename}')
print('== 解压落盘清单 ==')
for root,_,files in os.walk(d):
    for f in files:
        p=os.path.join(root,f)
        print(f'{os.path.getsize(p)}\t{p}')