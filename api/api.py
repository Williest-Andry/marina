import asyncio
import os
from typing import AsyncIterator, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
import httpx
import subprocess
import urllib.parse
import re


ngrok_public_url: Optional[str] = None
NGROK_API_URL = os.environ.get("NGROK_API_URL", "http://127.0.0.1:4040/api/tunnels")
NGROK_POLL_INTERVAL = float(os.environ.get("NGROK_POLL_INTERVAL", "5.0"))

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    print("Starting background task to poll ngrok URL")
    task = asyncio.create_task(_poll_ngrok_public_url())
    yield
  
    print("Cancelling ngrok polling task")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="Marina API (fastapi lifespam version)",
    version="0.1",
    lifespan=lifespan  
)

async def _poll_ngrok_public_url():
    global ngrok_public_url
    async with httpx.AsyncClient(timeout=3.0) as client:
        while True:
            try:
                r = await client.get(NGROK_API_URL)
                if r.status_code == 200:
                    data = r.json()
                    tunnels = data.get("tunnels", [])
                    pu = next((t.get("public_url") for t in tunnels if t.get("public_url", "").startswith("https://")), None)
                    ngrok_public_url = pu.rstrip("/") if pu else (tunnels[0].get("public_url").rstrip("/") if tunnels else None)
                else:
                    ngrok_public_url = None
            except Exception:
                ngrok_public_url = None
            await asyncio.sleep(NGROK_POLL_INTERVAL)

def _is_local_host(host: Optional[str]) -> bool:
    if not host:
        return False
    hostname = host.split(":", 1)[0].lower()
    return hostname in ("127.0.0.1", "localhost", "::1")

@app.middleware("http")
async def redirect_local(request: Request, call_next):
    global ngrok_public_url
    host = request.headers.get("host", "")
    if _is_local_host(host) and ngrok_public_url:
        path = request.url.path
        qs = request.scope.get("query_string", b"").decode(errors="ignore")
        url = ngrok_public_url + path + (f"?{qs}" if qs else "")
        return RedirectResponse(url=url, status_code=307)
    return await call_next(request)

@app.get("/")
async def root():
    return {"message": "Marina API. Formulas accepted via /marina?formula=..."}

@app.get("/marina")
async def marina_endpoint(request: Request):
    raw = request.scope.get("query_string", b"").decode("utf-8", errors="replace")
    if not raw or "formula=" not in raw:
        raise HTTPException(status_code=400, detail="Missing formula parameter")
    after = raw.split("formula=", 1)[1]
    m = re.search(r"&[A-Za-z0-9_]+=", after)
    candidate = after[:m.start()] if m else after
    if not candidate:
        raise HTTPException(status_code=400, detail="Empty formula")
    formula = urllib.parse.unquote_plus(candidate).strip()
    if not formula:
        raise HTTPException(status_code=400, detail="Empty formula after decode")
    if len(formula) > 50000:
        raise HTTPException(status_code=400, detail="Formula too long")
    cmd = ["/usr/local/bin/marina", formula]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timeout from marina")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Marina binary not found")
    return completed.stdout.strip()
