"""Prüft in Edge/Chromium (headless), ob der Service Worker registriert wird und offline funktioniert."""
import asyncio, json, subprocess, sys, time, urllib.request
import websockets

EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
PROFIL = sys.argv[1]
URL = "http://localhost:8080/"

async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", "--remote-debugging-port=9333", f"--user-data-dir={PROFIL}",
                             "--no-first-run", "--disable-gpu", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                tabs = json.load(urllib.request.urlopen("http://localhost:9333/json"))
                break
            except Exception:
                time.sleep(0.5)
        ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
        async with websockets.connect(ws_url, max_size=None) as ws:
            n = 0
            async def cmd(method, **params):
                nonlocal n
                n += 1
                await ws.send(json.dumps({"id": n, "method": method, "params": params}))
                while True:
                    m = json.loads(await ws.recv())
                    if m.get("id") == n:
                        return m.get("result", m.get("error"))
            async def js(expr):
                r = await cmd("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
                return r.get("result", {}).get("value", r)
            await cmd("Page.enable"); await cmd("Network.enable")
            await cmd("Page.navigate", url=URL + "#/rezept/kuerbissuppe")
            await asyncio.sleep(3)
            ergebnis = {}
            ergebnis["registriert"] = await js("navigator.serviceWorker.ready.then(r => !!r.active)")
            await asyncio.sleep(1)
            ergebnis["caches"] = await js("caches.keys().then(k => k)")
            ergebnis["im_cache"] = await js("caches.open('ruehrwerk-v1').then(c => c.keys()).then(k => k.map(r => new URL(r.url).pathname))")
            # Offline gehen und neu laden
            await cmd("Network.emulateNetworkConditions", offline=True, latency=0, downloadThroughput=0, uploadThroughput=0)
            await cmd("Page.reload")
            await asyncio.sleep(3)
            ergebnis["offline_titel"] = await js("document.title")
            ergebnis["offline_text"] = await js("document.body.innerText.slice(0, 80)")
            print(json.dumps(ergebnis, ensure_ascii=False, indent=1))
    finally:
        proc.terminate()

asyncio.run(main())
