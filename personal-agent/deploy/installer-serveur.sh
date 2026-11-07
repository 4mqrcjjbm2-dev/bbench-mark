#!/usr/bin/env bash
# Installe et lance Jarvis sur un serveur Linux (Ubuntu/Debian) : Jarvis + Ollama + SearXNG.
# Usage : ./deploy/installer-serveur.sh [modele]     ex. ./deploy/installer-serveur.sh qwen3:14b
# Sans modèle donné : le modèle conseillé pour la mémoire de la machine est choisi.
set -euo pipefail
cd "$(dirname "$0")/.."
MODELE="${1:-}"

echo "== 1/6  Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER" || true
fi
DOCKER="docker"; docker info >/dev/null 2>&1 || DOCKER="sudo docker"

echo "== 2/6  Configuration (.env)"
if [ ! -f .env ]; then
  cp .env.example .env
  jeton=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  secret=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  sed -i "s|^AGENT_TOKEN=.*|AGENT_TOKEN=${jeton}|" .env
  echo "SEARXNG_SECRET=${secret}" >> .env
  echo "   Jeton de la page Jarvis : ${jeton}   (garde-le précieusement)"
fi
if [ -z "$MODELE" ] && ! grep -qE '^AGENT_MODEL=.+' .env; then
  # Choix automatique selon la mémoire vive (le même calcul que l'écran « État du serveur »).
  ram=$(awk '/MemTotal/{printf "%d", $2/1048576}' /proc/meminfo 2>/dev/null || echo 8)
  if   [ "$ram" -ge 30 ]; then MODELE="qwen3:14b"
  elif [ "$ram" -ge 14 ]; then MODELE="qwen3:8b"
  elif [ "$ram" -ge 7 ];  then MODELE="qwen3:4b"
  else MODELE="qwen3:1.7b"; fi
  echo "   Mémoire : ${ram} Go → modèle conseillé : ${MODELE}"
fi
if [ -n "$MODELE" ]; then sed -i "s|^AGENT_MODEL=.*|AGENT_MODEL=${MODELE}|" .env; fi
MODELE=$(grep -E '^AGENT_MODEL=' .env | cut -d= -f2-); MODELE="${MODELE:-qwen3:8b}"
mkdir -p data atelier

echo "== 3/6  Mémoire du Cerveau (optionnel)"
CERVEAU="${CERVEAU_DIR:-$HOME/cerveaux-}"
if [ ! -d "$CERVEAU/.git" ]; then
  read -r -p "   Cloner ton Cerveau (dépôt GitHub privé 4mqrcjjbm2-dev/cerveaux-) ? (o/n) " rep || rep="n"
  if [ "$rep" = "o" ]; then
    git clone https://github.com/4mqrcjjbm2-dev/cerveaux- "$CERVEAU" \
      || echo "   Échec : connecte d'abord GitHub (gh auth login), puis relance ce script."
  fi
fi
if [ -d "$CERVEAU/.git" ]; then
  printf 'services:\n  jarvis:\n    volumes:\n      - %s:/cerveau\n' "$CERVEAU" > docker-compose.override.yml
  if grep -q '^AGENT_CERVEAU_DIR=' .env; then sed -i 's|^AGENT_CERVEAU_DIR=.*|AGENT_CERVEAU_DIR=/cerveau|' .env
  else echo "AGENT_CERVEAU_DIR=/cerveau" >> .env; fi
  # Le conteneur n'a pas tes identifiants GitHub : il enregistre la mémoire en local (commit).
  # Pour l'envoyer sur GitHub : git -C "$CERVEAU" push   (voir INSTALLATION.md).
  if grep -q '^AGENT_CERVEAU_PUSH=' .env; then sed -i 's|^AGENT_CERVEAU_PUSH=.*|AGENT_CERVEAU_PUSH=0|' .env
  else echo "AGENT_CERVEAU_PUSH=0" >> .env; fi
  echo "   Cerveau branché : $CERVEAU"
fi

echo "== 4/6  Démarrage des services"
$DOCKER compose up -d --build

echo "== 5/6  Modèle IA : ${MODELE}"
case "$MODELE" in
  *-cloud|*:cloud) echo "   Modèle cloud Ollama (selon ton abonnement Ollama) : connecte ton compte avec"
                   echo "   $DOCKER compose exec ollama ollama signin" ;;
  *) $DOCKER compose exec -T ollama ollama pull "$MODELE" ;;
esac
LEGER=$(grep -E '^AGENT_MODELE_LEGER=' .env | cut -d= -f2-)
if [ -n "$LEGER" ] && [ "$LEGER" != "$MODELE" ]; then
  case "$LEGER" in *-cloud|*:cloud) ;; *) $DOCKER compose exec -T ollama ollama pull "$LEGER" ;; esac
fi

echo "== 6/6  Accès depuis l'iPhone"
if command -v tailscale >/dev/null; then
  sudo tailscale serve --bg 8787 && tailscale serve status || true
else
  echo "   Installe Tailscale (open source côté appareil) : curl -fsSL https://tailscale.com/install.sh | sh"
  echo "   puis : sudo tailscale up  et  sudo tailscale serve --bg 8787"
fi

echo
echo "Jarvis tourne. Sur le serveur : http://127.0.0.1:8787   ·   Sur l'iPhone : l'adresse https://…ts.net de Tailscale."
echo "Diagnostic complet :"
./deploy/verifier.sh || true
