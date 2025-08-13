#!/usr/bin/env bash
set -euo pipefail

echo "Configuring ngrok..."
ngrok config add-authtoken "${NGROK_AUTH_KEY}"

echo "Starting ngrok in background (forward to port 8081)..."
ngrok http 8081 --log=stdout &>/dev/null &
NGROK_PID=$!

cleanup() {
  echo "Shutting down ngrok (PID ${NGROK_PID})..."
  kill "${NGROK_PID}" 2>/dev/null || true
  wait "${NGROK_PID}" 2>/dev/null || true
}
trap cleanup EXIT

# Wait public tunnel 
WAIT_FOR_NGROK_SECONDS="${WAIT_FOR_NGROK_SECONDS:-60}"
WAIT_SECONDS="$(printf '%d' "$WAIT_FOR_NGROK_SECONDS")"
echo "Waiting up to ${WAIT_SECONDS}s for ngrok public URL..."

PUBLIC_URL=""
for ((i=1; i<=WAIT_SECONDS; i++)); do
  sleep 1
  RAW=$(curl -s http://127.0.0.1:4040/api/tunnels || true)
  PUBLIC_URL=$(printf '%s' "$RAW" | python3 -c '
import sys, json
raw = sys.stdin.read()
try:
    data = json.loads(raw)
except:
    sys.exit(0)
tunnels = data.get("tunnels", [])
for t in tunnels:
    pu = t.get("public_url", "")
    if pu.startswith("https://"):
        print(pu)
        sys.exit(0)
if tunnels:
    print(tunnels[0].get("public_url",""))
else:
    sys.exit(0)
')
  PUBLIC_URL="$(echo -n "$PUBLIC_URL" | tr -d "\r\n")"
  if [ -n "$PUBLIC_URL" ]; then
    echo "Connected! ngrok URL: ${PUBLIC_URL}"
    echo "THIS IS THE ONLY AVALAIBLE URL, LOCAL URL (127.0.0.1) IS LOCKED !!"
    break
  fi
done

if [ -z "$PUBLIC_URL" ]; then
  echo "⚠ ngrok tunnel not ready after $WAIT_SECONDS seconds."
  echo "Proceeding to start uvicorn regardless."
fi

echo "Starting uvicorn (FastAPI)..."
echo "THE LOCAL URL BELOW IS NOT AVALAIBLE !!"
exec uvicorn api:app --host 0.0.0.0 --port 8081
