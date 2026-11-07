#!/usr/bin/env bash
# Claude Code SUR CET ORDINATEUR, avec le moteur IA d'Ollama : gratuit avec un modèle local, et sans Internet.
# Il s'ouvre dans ton Cerveau (sa mémoire, ses compétences) avec accès au code de Jarvis.
# Usage : ./deploy/claude-local.sh [modèle]        ex. ./deploy/claude-local.sh qwen3:14b   ou   kimi-k3:cloud
# Réf. : https://docs.ollama.com/api/anthropic-compatibility
set -euo pipefail
cd "$(dirname "$0")/.."
JARVIS="$(pwd)"
val() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2-; }
MODELE="${1:-$(val AGENT_MODELE_RENFORT)}"; MODELE="${MODELE:-$(val AGENT_MODEL)}"; MODELE="${MODELE:-qwen3:8b}"

if ! command -v claude >/dev/null; then
  echo "Installation de Claude Code (une fois, Internet nécessaire)…"
  curl -fsSL https://claude.ai/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
fi
curl -fsS -m 5 http://127.0.0.1:11434/api/tags >/dev/null || { echo "Ollama ne répond pas sur 127.0.0.1:11434 : lance d'abord ./deploy/installer-serveur.sh"; exit 1; }

CERVEAU="${CERVEAU_DIR:-$HOME/cerveaux-}"
if [ -d "$CERVEAU/.git" ]; then DOSSIER="$CERVEAU"; else DOSSIER="$JARVIS"; echo "(Cerveau introuvable dans $CERVEAU : Claude s'ouvre dans le code de Jarvis.)"; fi
echo "Claude Code · modèle $MODELE via Ollama · dossier $DOSSIER"
echo "Astuce : les petits modèles locaux codent moins bien ; pour un gros chantier, utilise ton modèle renfort."
cd "$DOSSIER"
ANTHROPIC_BASE_URL=http://127.0.0.1:11434 ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_API_KEY="" \
  exec claude --model "$MODELE" --add-dir "$JARVIS"
