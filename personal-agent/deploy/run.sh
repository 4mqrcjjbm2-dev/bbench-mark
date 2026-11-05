#!/usr/bin/env bash
# Installe (si besoin) puis lance le serveur de l'agent sur le port 8787.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
if [ ! -f .env ]; then
  echo "Crée d'abord le fichier .env (cp .env.example .env) et remplis-le." >&2
  exit 1
fi
exec .venv/bin/uvicorn agent.server:app --host 0.0.0.0 --port "${PORT:-8787}"
