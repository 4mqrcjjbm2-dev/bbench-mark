#!/usr/bin/env bash
# Télécharge Wikipédia (et d'autres encyclopédies) pour que Jarvis s'en serve HORS LIGNE, puis démarre Kiwix.
# Usage : ./deploy/telecharger-savoir.sh [petit|moyen|complet] [wiktionnaire]
#   petit   = résumés des articles (le plus léger)
#   moyen   = articles complets sans images (recommandé)
#   complet = articles complets avec images (le plus lourd)
set -euo pipefail
cd "$(dirname "$0")/.."
TAILLE="${1:-moyen}"
case "$TAILLE" in
  petit) MOTIF="wikipedia_fr_all_mini" ;;
  moyen) MOTIF="wikipedia_fr_all_nopic" ;;
  complet) MOTIF="wikipedia_fr_all_maxi" ;;
  *) echo "Taille inconnue : petit, moyen ou complet"; exit 1 ;;
esac
mkdir -p zim

telecharger() {  # $1 = dossier sur download.kiwix.org, $2 = début du nom du fichier
  local base="https://download.kiwix.org/zim/$1/"
  local fichier
  fichier=$(curl -fsSL "$base" | grep -oE "${2}_[0-9]{4}-[0-9]{2}\.zim" | sort -u | tail -1)
  if [ -z "$fichier" ]; then echo "Introuvable : $2 dans $base"; return 1; fi
  local octets
  octets=$(curl -fsSIL "$base$fichier" | grep -i '^content-length' | tail -1 | tr -dc '0-9')
  echo "→ $fichier : $(( ${octets:-0} / 1024 / 1024 / 1024 )) Go environ"
  read -r -p "  Télécharger ? (o/n) " ok
  [ "$ok" = "o" ] || return 0
  wget -c -O "zim/$fichier" "$base$fichier"   # -c : reprend si la connexion coupe
}

telecharger wikipedia "$MOTIF"
if [ "${2:-}" = "wiktionnaire" ]; then telecharger wiktionary wiktionary_fr_all_nopic; fi

if ! grep -q '^KIWIX_URL=' .env 2>/dev/null; then echo "KIWIX_URL=http://kiwix:8080" >> .env; fi
DOCKER="docker"; docker info >/dev/null 2>&1 || DOCKER="sudo docker"
$DOCKER compose --profile savoir up -d kiwix
$DOCKER compose up -d jarvis   # Jarvis relit KIWIX_URL
echo "Le Savoir hors ligne est prêt : demande à Jarvis « Qu'est-ce que la Révolution tranquille ? »"
