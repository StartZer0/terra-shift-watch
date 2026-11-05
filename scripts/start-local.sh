#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ] || [ ! -d node_modules ]; then
  echo 'Install dependencies first: python3 -m venv .venv; .venv/bin/pip install -r requirements.lock.txt; npm ci'
  exit 1
fi
.venv/bin/python -m uvicorn services.api.app:app --host 127.0.0.1 --port 8018 &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true' EXIT INT TERM
npm run dev -- --port 5174 --strictPort
