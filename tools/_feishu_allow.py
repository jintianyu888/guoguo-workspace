import os
import json, sys
def _atomic_write(path, data):
    import os, tempfile
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".cfg-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=True, indent=1)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try: os.unlink(tmp)
        except Exception: pass
        raise

cfg, ag, ou = sys.argv[1:4]
c = json.load(open(cfg, encoding="utf-8"))
a = c["channels"]["feishu"]["accounts"][ag]
af = a.setdefault("allowFrom", [])
if ou in af:
    print("已在白名单")
    sys.exit(0)
af.append(ou)
_atomic_write(cfg, c)
print("已加入 allowFrom:", af)
