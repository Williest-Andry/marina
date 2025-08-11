from fastapi import FastAPI, HTTPException, Request
import subprocess
import urllib.parse
import re

app = FastAPI(title="Marina API", version="0.1")

KNOWN_QUERY_PARAMS = {"timeout", "mode", "foo"}

@app.get("/")
async def root():
    return {"message": "Marina API. GET /marina?formula=... (supports raw & encoded formulas)"}

@app.get("/marina")
async def marina_endpoint(request: Request):
    raw_qs_bytes = request.scope.get("query_string", b"")
    raw_qs = raw_qs_bytes.decode("utf-8", errors="replace")

    if not raw_qs:
        raise HTTPException(status_code=400, detail="no query string provided")

    if "formula=" not in raw_qs:
        raise HTTPException(status_code=400, detail="formula parameter missing")
    
    after = raw_qs.split("formula=", 1)[1]

    m = re.search(r'&[A-Za-z0-9_]+=', after)

    if m:
        candidate = after[: m.start() ]
    else:
        candidate = after

    if not candidate:
        raise HTTPException(status_code=400, detail="formula is empty after parsing")

    formula = urllib.parse.unquote_plus(candidate).strip()

    if not formula:
        raise HTTPException(status_code=400, detail="formula is empty after decode")
    if len(formula) > 50_000:
        raise HTTPException(status_code=400, detail="formula too large")

    cmd = ["/usr/local/bin/marina", formula]

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="marina timeout")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="marina binary not found inside container")

    return completed.stdout[:-1]