"""Real-browser smoke/E2E checks for Stage 5A.1 using Chrome DevTools Protocol.

It uses a disposable session root, so no human or production reference is created.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from tools.vertical_reference_app.core import VerticalReferenceSession
from tools.vertical_reference_app.server import create_server


CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


class CDP:
    def __init__(self, url: str) -> None:
        host = url.split("//", 1)[1].split("/", 1)[0]
        path = "/" + url.split("/", 3)[3]
        self.sock = socket.create_connection((host.split(":")[0], int(host.split(":")[1])))
        key = base64.b64encode(os.urandom(16)).decode()
        handshake = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nOrigin: http://127.0.0.1\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode()
        self.sock.sendall(handshake)
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.sock.recv(4096)
        if b"101 " not in response:
            raise RuntimeError(f"Chrome CDP websocket handshake failed: {response[:300]!r}")
        self.message_id = 0

    def close(self) -> None:
        self.sock.close()

    def _send(self, payload: str) -> None:
        data = payload.encode()
        mask = os.urandom(4)
        length = len(data)
        if length < 126:
            header = bytes([0x81, 0x80 | length])
        elif length < 65536:
            header = bytes([0x81, 0x80 | 126]) + length.to_bytes(2, "big")
        else:
            header = bytes([0x81, 0x80 | 127]) + length.to_bytes(8, "big")
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(data))
        self.sock.sendall(header + mask + masked)

    def _recv(self) -> str:
        header = self.sock.recv(2)
        length = header[1] & 0x7F
        if length == 126:
            length = int.from_bytes(self.sock.recv(2), "big")
        if length == 127:
            length = int.from_bytes(self.sock.recv(8), "big")
        if header[1] & 0x80:
            mask = self.sock.recv(4)
        else:
            mask = None
        data = self.sock.recv(length)
        if mask:
            data = bytes(value ^ mask[index % 4] for index, value in enumerate(data))
        return data.decode()

    def evaluate(self, expression: str) -> object:
        self.message_id += 1
        self._send(json.dumps({"id": self.message_id, "method": "Runtime.evaluate", "params": {"expression": expression, "returnByValue": True, "awaitPromise": True}}))
        while True:
            payload = json.loads(self._recv())
            if payload.get("id") == self.message_id:
                result = payload.get("result", {}).get("result", {})
                if "exceptionDetails" in payload.get("result", {}):
                    raise RuntimeError(str(payload["result"]["exceptionDetails"]))
                return result.get("value")


def wait_json(url: str) -> object:
    for _ in range(50):
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return json.loads(response.read())
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for {url}")


def main() -> int:
    if not CHROME.is_file():
        raise RuntimeError("Google Chrome is required for the browser E2E")
    state_root = Path(tempfile.mkdtemp(prefix="stage5a1-e2e-"))
    server = create_server(VerticalReferenceSession("nivel_a2_01", state_root=state_root), 8777)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    profile = Path(tempfile.mkdtemp(prefix="stage5a1-chrome-"))
    chrome = subprocess.Popen([str(CHROME), "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={profile}", "--remote-debugging-port=9223", "--remote-allow-origins=*", "--no-first-run", "--no-default-browser-check"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cdp = None
    try:
        wait_json("http://127.0.0.1:9223/json/version")
        for existing in wait_json("http://127.0.0.1:9223/json/list"):
            if existing.get("type") == "page":
                urllib.request.urlopen(f"http://127.0.0.1:9223/json/close/{existing['id']}", timeout=5).read()
        target = urllib.request.Request("http://127.0.0.1:9223/json/new?http://127.0.0.1:8777/", method="PUT")
        with urllib.request.urlopen(target, timeout=5) as response:
            target_payload = json.loads(response.read())
        cdp = CDP(target_payload["webSocketDebuggerUrl"])
        cdp.evaluate("new Promise(r => setTimeout(r, 500))")
        assert cdp.evaluate("document.querySelectorAll('[data-zoom]').length") == 6
        initial_url = cdp.evaluate("location.href")
        for zoom in ("1", "1.5", "2", "3", "5") * 4:
            cdp.evaluate(f"document.querySelector('[data-zoom=\\\"{zoom}\\\"]').click()")
        pages = wait_json("http://127.0.0.1:9223/json/list")
        assert len([page for page in pages if page.get("type") == "page"]) == 1
        assert cdp.evaluate("location.href") == initial_url

        click_center = """(() => { const v=document.querySelector('#viewport'),r=v.getBoundingClientRect(); const x=r.left+r.width/2,y=r.top+r.height/2; v.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:x,clientY:y})); v.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,clientX:x,clientY:y})); return !document.querySelector('#confirm').disabled; })()"""
        cdp.evaluate("document.querySelector('[data-zoom=\"2\"]').click(); document.querySelector('#modeMark').click()")
        assert cdp.evaluate(click_center) is True
        assert cdp.evaluate("document.querySelector('#message').textContent.includes('provisional')") is True
        cdp.evaluate("document.querySelector('#correct').click()")
        assert cdp.evaluate("document.querySelector('#confirm').disabled") is True
        cdp.evaluate("document.querySelector('#modePan').click(); document.querySelector('[data-zoom=\"3\"]').click()")
        before = cdp.evaluate("document.querySelector('#stepCounter').textContent")
        cdp.evaluate("(() => { const v=document.querySelector('#viewport'),r=v.getBoundingClientRect(); const x=r.left+200,y=r.top+200; v.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:x,clientY:y})); v.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,clientX:x+40,clientY:y+20})); v.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,clientX:x+40,clientY:y+20})); })()")
        assert cdp.evaluate("document.querySelector('#stepCounter').textContent") == before
        cdp.evaluate("document.querySelector('#modeMark').click(); document.querySelector('[data-zoom=\"5\"]').click()")
        assert cdp.evaluate(click_center) is True
        cdp.evaluate("location.reload()")
        cdp.evaluate("new Promise(r => setTimeout(r, 500))")
        assert cdp.evaluate("document.querySelector('#confirm').disabled") is True
        # Disposable backend flow: two real browser clicks and confirmations.
        cdp.evaluate("document.querySelector('[data-zoom=\"1\"]').click(); document.querySelector('#modeMark').click()")
        click_canonical = """async ([u,v]) => { const el=document.querySelector('#viewport'),r=el.getBoundingClientRect(),s=Math.min(r.width/2746,r.height/1536),l=(r.width-2746*s)/2,t=(r.height-1536*s)/2,x=r.left+l+u*s,y=r.top+t+v*s; el.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:x,clientY:y})); el.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,clientX:x,clientY:y})); await new Promise(r=>setTimeout(r,80)); document.querySelector('#confirm').click(); await new Promise(r=>setTimeout(r,120)); return document.querySelector('#stepCounter').textContent; }"""
        assert cdp.evaluate(f"({click_canonical})([1373,693])") == "Paso 2 de 4"
        assert cdp.evaluate(f"({click_canonical})([1373,584])") == "Paso 3 de 4"
        cdp.evaluate("fetch('/api/reference/reset',{method:'POST'})")
        print("BROWSER_E2E_PASS: one_tab, zoom_100_200_500, provisional_correct, pan_mode, refresh, step1_to_step2")
        return 0
    finally:
        if cdp:
            cdp.close()
        chrome.terminate()
        chrome.wait(timeout=5)
        server.shutdown()
        server.server_close()
        shutil.rmtree(profile, ignore_errors=True)
        shutil.rmtree(state_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
