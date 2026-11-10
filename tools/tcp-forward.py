import asyncio, sys
DST_PORT = 18789
LISTEN_PORT = 18790
async def pipe(r, w):
    try:
        while True:
            d = await r.read(65536)
            if not d: break
            w.write(d); await w.drain()
    except Exception: pass
    finally:
        try: w.close()
        except Exception: pass
async def handle(cr, cw):
    try:
        sr, sw = await asyncio.open_connection('127.0.0.1', DST_PORT)
    except Exception:
        cw.close(); return
    await asyncio.gather(pipe(cr, sw), pipe(sr, cw))
async def main():
    s = await asyncio.start_server(handle, '0.0.0.0', LISTEN_PORT)
    print('forwarding 0.0.0.0:%d -> 127.0.0.1:%d' % (LISTEN_PORT, DST_PORT), flush=True)
    async with s:
        await s.serve_forever()
asyncio.run(main())
