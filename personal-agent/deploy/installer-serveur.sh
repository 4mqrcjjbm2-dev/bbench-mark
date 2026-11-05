#!/usr/bin/env bash
# Installe et lance Jarvis sur un serveur Linux (Ubuntu/Debian) : Jarvis + Ollama + SearXNG.
# Usage : ./deploy/installer-serveur.sh [modele]     ex. ./deploy/installer-serveur.sh qwen3:14b
set -euo pipefail
cd "$(dirname "$0")/.."
MODELE="${1:-}"

echo "== 1/5  Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER" || true
fi
DOCKER="docker"; docker info >/dev/null 2>&1 || DOCKER="sudo docker"

echo "== 2/5  Configuration (.env)"
if [ ! -f .env ]; then
  cp .env.example .env
  jeton=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  secret=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  sed -i "s|^AGENT_TOKEN=.*|AGENT_TOKEN=${jeton}|" .env
  echo "SEARXNG_SECRET=${secret}" >> .env
  echo "   Jeton de la page Jarvis : ${jeton}   (garde-le précieusement)"
fi
if [ -n "$MODELE" ]; then sed -i "s|^AGENT_MODEL=.*|AGENT_MODEL=${MODELE}|" .env; fi
MODELE=$(grep -E '^AGENT_MODEL=' .env | cut -d= -f2-); MODELE="${MODELE:-qwen3:8b}"
mkdir -p data atelier

echo "== 3/5  Démarrage des services"
$DOCKER compose up -d --build

echo "== 4/5  Modèle IA libre : ${MODELE}"
case "$MODELE" in
  *-cloud|*:cloud) echo "   Modèle cloud Ollama : connecte ton compte gratuit avec"
                   echo "   $DOCKER compose exec ollama ollama signin" ;;
  *) $DOCKER compose exec -T ollama ollama pull "$MODELE" ;;
esac
LEGER=$(grep -E '^AGENT_MODELE_LEGER=' .env | cut -d= -f2-)
if [ -n "$LEGER" ] && [ "$LEGER" != "$MODELE" ]; then
  case "$LEGER" in *-cloud|*:cloud) ;; *) $DOCKER compose exec -T ollama ollama pull "$LEGER" ;; esac
fi

echo "== 5/5  Accès depuis l'iPhone"
if command -v tailscale >/dev/null; then
  sudo tailscale serve --bg 8787 && tailscale serve status || true
else
  echo "   Installe Tailscale (open source côté appareil) : curl -fsSL https://tailscale.com/install.sh | sh"
  echo "   puis : sudo tailscale up  et  sudo tailscale serve --bg 8787"
fi
echo
echo "Jarvis tourne. Sur le serveur : http://127.0.0.1:8787   ·   Sur l'iPhone : l'adresse https://…ts.net de Tailscale."
