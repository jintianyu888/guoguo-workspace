import json, sys, urllib.request
want = ["nvidia-cublas-cu12", "nvidia-cudnn-cu12"]
urls = []
for pk in want:
    d = json.load(urllib.request.urlopen("https://pypi.org/pypi/%s/json" % pk, timeout=25))
    cand = [f["url"] for f in d["urls"]
            if f["filename"].endswith(".whl") and "manylinux" in f["filename"] and "x86_64" in f["filename"]]
    if not cand:
        print("NO_X86_64", pk); sys.exit(1)
    urls.append(cand[0])
    print("OK", pk, cand[0].split("/")[-1][:70])
open("state/wheel-urls.txt", "w").write("\n".join(urls))