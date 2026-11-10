import urllib.request, re, json
out = {}
for k, pkg in [("cudnn", "nvidia-cudnn-cu12"), ("torch", "torch")]:
    try:
        html = urllib.request.urlopen(f"https://pypi.tuna.tsinghua.edu.cn/simple/{pkg}/", timeout=25).read().decode("utf-8","ignore")
        hrefs = re.findall(r'href="([^"#]+\.whl)', html)
        cand = [h for h in hrefs if "x86_64" in h and ("cu12" in h or pkg == "torch")]
        # 取文件名里版本号最大的
        def ver(h):
            m = re.search(r"-(\d+(?:\.\d+)+)-", h.split("/")[-1])
            return [int(x) for x in m.group(1).split(".")] if m else [0]
        cand.sort(key=ver)
        if cand:
            h = cand[-1]
            if h.startswith("../"): h = "https://pypi.tuna.tsinghua.edu.cn/" + h.lstrip("./")
            out[k] = h
            print(k, h.split("/")[-1][:70])
    except Exception as e:
        print(k, "ERR", e)
json.dump(out, open("/home/j/.openclaw/workspace/state/mirror-wheel-urls.json","w"), ensure_ascii=False)