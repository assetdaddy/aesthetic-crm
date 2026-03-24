#!/usr/bin/env bash
set -euo pipefail

# Render injects PORT automatically. The same script also works locally.
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
