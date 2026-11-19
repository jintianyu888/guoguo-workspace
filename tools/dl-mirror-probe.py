import urllib.request, re, json, subprocess
PKGS = {"cudnn": "nvidia-cudnn-cu12", "torch": "torch"}
out = {}
for k, pkg in PKGS.items():
    try:
        html = urllib.request.urlopen(f"https://pypi.tuna.tsinghua.edu.cn/simple/{pkg}/", timeout=25).read().decode("utf-8","ignore")
        hrefs = re.findall(r'href="([^"#]+\.whl)', html)
        cand = [h for h in hrefs if "x86_64" in h] or [h for h in hrefs if "manylinux" in h]
        if cand:
            h = cand[-1]
            if h.startswith("../"):
                h = "https://pypi.tuna.tsinghua.edu.cn/" + h.lstrip("./")
            out[k] = h
            print(k, "OK", h[:105])
        else:
            print(k, "无候选（共 %d 个 whl 链接）" % len(hrefs))
    except Exception as e:
        print(k, "ERR", e)
json.dump(out, open("state/mirror-wheel-urls.json","w"), ensure_ascii=False)
print("---- 镜像测速（30MB 范围 / 12 秒）----")
for k, u in out.items():
    r = subprocess.run(["curl","-s","-o","/dev/null","-w","%{speed_download}","-r","0-30000000","--max-time","12",u], capture_output=True, text=True, timeout=20)
    try: print(f"{k}: {float(r.stdout or 0)/1048576:.2f} MB/s")
    except Exception: print(k, "测不出")