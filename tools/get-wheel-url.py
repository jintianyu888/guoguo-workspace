import json, urllib.request
for pk in ["nvidia-cublas-cu12", "nvidia-cudnn-cu12"]:
    try:
        d = json.load(urllib.request.urlopen("https://pypi.org/pypi/%s/json" % pk, timeout=25))
        urls = [f["url"] for f in d["urls"] if f["filename"].endswith(".whl") and "manylinux" in f["filename"]]
        if urls:
            open("state/wheel-url.txt", "w").write(urls[0])
            print("OK", pk, urls[0][:70])
            break
    except Exception as e:
        print("ERR", pk, e)