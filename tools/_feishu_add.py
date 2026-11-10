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

cfg, ag, appid, sec, force = sys.argv[1:6]
c = json.load(open(cfg, encoding="utf-8"))
fe = c.setdefault("channels", {}).setdefault("feishu", {}).setdefault("accounts", {})
cur = fe.get(ag, {})
if cur.get("appId") and cur["appId"] != appid and force != "--force":
    print("拒绝: " + ag + " 已存在且 appId 不同，需 --force")
    sys.exit(3)
allow = cur.get("allowFrom") or []
if ag not in c.setdefault("agents", {}).setdefault("entries", {}):
    print("警告: agents.entries." + ag + " 不存在，本脚本只做渠道")
fe[ag] = {"enabled": True, "appId": appid,
         "appSecret": {"source": "store", "provider": "default", "id": sec},
         "connectionMode": "websocket", "dmPolicy": "allowlist", "allowFrom": allow}
bd = c.setdefault("bindings", [])
if not any(b.get("agentId") == ag and (b.get("match") or {}).get("accountId") == ag for b in bd):
    bd.append({"agentId": ag, "match": {"channel": "feishu", "accountId": ag}})
    print("已补 binding")
_atomic_write(cfg, c)
print("已写入 accounts." + ag + " appId=" + appid + " secretRef=" + sec + " allowFrom=" + str(allow or "空"))
