#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
command -v ffprobe >/dev/null || { echo 'Install FFmpeg (ffprobe is required to validate videos).'; exit 1; }
command -v uv >/dev/null || { echo 'Install uv to set up the isolated Python environment.'; exit 1; }
if [ ! -x .venv/bin/python ]; then uv venv .venv --python 3.12; fi
uv pip install --python .venv/bin/python -r services/analysis/requirements.lock -e services/analysis
(cd apps/web && npm ci --no-audit --no-fund)
pids=()
cleanup(){ for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM
.venv/bin/python -m uvicorn analysis.main:app --host 127.0.0.1 --port 8000 &
pids+=("$!")
.venv/bin/python -m analysis.worker &
pids+=("$!")
(cd apps/web && npm run dev -- --hostname 127.0.0.1) &
pids+=("$!")
echo 'Winner Signal: http://localhost:3000 — private local instance'
wait
