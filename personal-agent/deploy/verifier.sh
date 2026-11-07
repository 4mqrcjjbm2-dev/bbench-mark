#!/usr/bin/env bash
# Diagnostic de l'installation de Jarvis : ce qui marche, ce qui manque, et comment le régler.
# Usage : ./deploy/verifier.sh
cd "$(dirname "$0")/.."
ok()  { printf "  \033[32m✔\033[0m %s\n" "$1"; }
non() { printf "  \033[31m✘\033[0m %s\n      → %s\n" "$1" "$2"; PROBLEMES=$((PROBLEMES+1)); }
info(){ printf "  · %s\n" "$1"; }
PROBLEMES=0
DOCKER="docker"; docker info >/dev/null 2>&1 || DOCKER="sudo docker"
val() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2-; }

echo "== Machine"
info "Mémoire : $(free -g 2>/dev/null | awk '/Mem:/{print $2" Go (libre : "$7" Go)"}')"
info "Disque libre : $(df -h . | awk 'NR==2{print $4}')"
if command -v nvidia-smi >/dev/null; then info "Carte graphique : $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)"; else info "Carte graphique : aucune NVIDIA détectée (le modèle tournera sur le processeur)"; fi

echo "== Configuration"
[ -f .env ] && ok ".env présent" || non ".env manquant" "lance ./deploy/installer-serveur.sh"
T=$(val AGENT_TOKEN); [ ${#T} -ge 24 ] && ok "jeton de la page défini" || non "AGENT_TOKEN absent ou trop court" "relance l'installateur ou génère-en un (24 caractères minimum)"
M=$(val AGENT_MODEL); info "Modèle principal : ${M:-qwen3:8b}   léger : $(val AGENT_MODELE_LEGER)   renfort : $(val AGENT_MODELE_RENFORT)"

echo "== Services"
command -v docker >/dev/null && ok "Docker installé" || non "Docker absent" "curl -fsSL https://get.docker.com | sh"
for s in jarvis ollama searxng; do
  if $DOCKER compose ps --status running --services 2>/dev/null | grep -qx "$s"; then ok "$s tourne"; else non "$s ne tourne pas" "$DOCKER compose up -d $s   puis   $DOCKER compose logs $s"; fi
done
curl -fsS -m 5 http://127.0.0.1:8787/health >/dev/null && ok "la page Jarvis répond (http://127.0.0.1:8787)" || non "la page Jarvis ne répond pas" "$DOCKER compose logs --tail 50 jarvis"

echo "== Moteur IA"
LISTE=$($DOCKER compose exec -T ollama ollama list 2>/dev/null)
for m in "${M:-qwen3:8b}" "$(val AGENT_MODELE_LEGER)"; do
  [ -z "$m" ] && continue
  case "$m" in *cloud) info "$m est un modèle cloud (connexion : $DOCKER compose exec ollama ollama signin)";; *)
    echo "$LISTE" | grep -q "^$m" && ok "modèle $m téléchargé" || non "modèle $m absent" "$DOCKER compose exec ollama ollama pull $m";; esac
done

echo "== Recherche et savoir"
$DOCKER compose exec -T jarvis python -c "import httpx,sys; r=httpx.get('http://searxng:8080/search',params={'q':'test','format':'json'},timeout=15); sys.exit(0 if r.status_code==200 else 1)" 2>/dev/null \
  && ok "SearXNG répond en JSON" || non "SearXNG ne répond pas en JSON" "vérifie deploy/searxng/settings.yml (formats: json) puis $DOCKER compose restart searxng"
if [ -n "$(val KIWIX_URL)" ]; then
  $DOCKER compose --profile savoir ps --status running --services 2>/dev/null | grep -qx kiwix && ok "Wikipédia hors ligne (Kiwix) tourne" || non "Kiwix ne tourne pas" "./deploy/telecharger-savoir.sh moyen"
  ls zim/*.zim >/dev/null 2>&1 && info "Encyclopédies : $(ls zim/*.zim | xargs -n1 basename | tr '\n' ' ')"
else info "Wikipédia hors ligne pas encore installé (optionnel) : ./deploy/telecharger-savoir.sh moyen"; fi

echo "== Mémoire du Cerveau"
if [ -n "$(val AGENT_CERVEAU_DIR)" ]; then ok "Cerveau branché"; else info "Cerveau pas branché (optionnel) : voir INSTALLATION.md, étape 5"; fi

echo "== Accès depuis l'iPhone"
if command -v tailscale >/dev/null; then tailscale serve status 2>/dev/null | grep -q 8787 && ok "Tailscale publie Jarvis" || non "Tailscale ne publie pas Jarvis" "sudo tailscale serve --bg 8787"
else info "Tailscale absent : l'iPhone peut ouvrir http://$(hostname -I 2>/dev/null | awk '{print $1}'):8787 sur le même Wi-Fi (après avoir ouvert le port), ou installe Tailscale"; fi

echo
[ "$PROBLEMES" -eq 0 ] && echo "Tout est prêt." || echo "$PROBLEMES point(s) à régler ci-dessus. Envoie ce rapport à Claude si tu bloques."
