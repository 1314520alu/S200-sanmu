import asyncio, json, sys, uuid
from datetime import datetime, timezone

try:
    import websockets
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets", "-q"])
    import websockets

HOST, PORT = "127.0.0.1", 9050
clients = set()
queue = asyncio.Queue()
log_path = r"G:\soft\S200工程\mcp\s200_lceda\_bridge9050.log"
hello = {"value": None}

def log(msg):
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}\n"
    print(line, end="", flush=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)

async def worker():
    while True:
        item = await queue.get()
        method, params, fut = item["method"], item["params"], item["fut"]
        try:
            # wait for a client up to 15s
            for _ in range(150):
                if clients:
                    break
                await asyncio.sleep(0.1)
            if not clients:
                raise RuntimeError("no bridge client within 15s")
            ws = next(iter(clients))
            rid = uuid.uuid4().hex
            req = {"type": "request", "id": rid, "method": method, "params": params or {}}
            # waiter for this id
            done = asyncio.get_event_loop().create_future()
            ws._pending = getattr(ws, "_pending", {})
            ws._pending[rid] = done
            await ws.send(json.dumps(req, ensure_ascii=False))
            log(f"SEND {method} id={rid}")
            resp = await asyncio.wait_for(done, timeout=item.get("timeout", 60))
            if not fut.done():
                fut.set_result(resp)
        except Exception as e:
            if not fut.done():
                fut.set_exception(e)
        finally:
            queue.task_done()

async def handler(ws):
    clients.add(ws)
    ws._pending = {}
    log(f"CONNECT clients={len(clients)}")
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except Exception:
                log(f"BADJSON {raw[:200]}")
                continue
            typ = msg.get("type")
            log(f"RECV {typ} {json.dumps(msg, ensure_ascii=False)[:600]}")
            if typ == "hello":
                hello["value"] = msg
                # handshake confirm with unique id
                rid = uuid.uuid4().hex
                req = {"type": "request", "id": rid, "method": "ping", "params": {}}
                done = asyncio.get_event_loop().create_future()
                ws._pending[rid] = done
                await ws.send(json.dumps(req))
                log(f"SEND ping(handshake) id={rid}")
            elif typ == "response":
                rid = str(msg.get("id", ""))
                pending = getattr(ws, "_pending", {})
                fut = pending.pop(rid, None)
                if fut and not fut.done():
                    fut.set_result(msg)
    except websockets.ConnectionClosed as e:
        log(f"CLOSE {e.code} {e.reason}")
    finally:
        clients.discard(ws)
        for fut in list(getattr(ws, "_pending", {}).values()):
            if not fut.done():
                fut.set_exception(RuntimeError("bridge disconnected"))
        log(f"DISCONNECT clients={len(clients)}")

async def http_api(reader, writer):
    try:
        data = await reader.read(262144)
        text = data.decode("utf-8", "replace")
        body = text.split("\r\n\r\n", 1)[-1]
        try:
            payload = json.loads(body) if body.strip() else {}
        except Exception:
            payload = {}
        method = payload.get("method") or "ping"
        params = payload.get("params") or {}
        timeout = float(payload.get("timeout", 60))
        fut = asyncio.get_event_loop().create_future()
        await queue.put({"method": method, "params": params, "fut": fut, "timeout": timeout})
        try:
            result = await asyncio.wait_for(fut, timeout=timeout + 5)
            resp = json.dumps({"ok": True, "result": result, "hello": hello["value"]}, ensure_ascii=False).encode()
            status = b"200 OK"
        except Exception as e:
            resp = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode()
            status = b"500 ERR"
        writer.write(b"HTTP/1.1 " + status + b"\r\nContent-Type: application/json\r\nContent-Length: " + str(len(resp)).encode() + b"\r\nConnection: close\r\n\r\n" + resp)
        await writer.drain()
    finally:
        writer.close()

async def main():
    open(log_path, "w", encoding="utf-8").write("")
    asyncio.create_task(worker())
    await websockets.serve(handler, HOST, PORT, ping_interval=20, ping_timeout=20)
    await asyncio.start_server(http_api, HOST, 9051)
    log(f"LISTEN ws://{HOST}:{PORT} http://{HOST}:9051/call")
    await asyncio.Future()

asyncio.run(main())
