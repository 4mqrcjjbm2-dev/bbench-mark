# Installer Jarvis — pas à pas

À suivre le jour où un ordinateur peut servir de serveur. Compte environ 1 h, surtout pour les téléchargements. Si une étape bloque, lance `./deploy/verifier.sh` et envoie le rapport à Claude.

## Ce qu'il faut
- Un ordinateur qui peut rester allumé. 16 Go de mémoire, c'est bien ; 8 Go, ça marche avec un petit modèle. Une carte graphique NVIDIA rend Jarvis beaucoup plus rapide.
- **Ubuntu** (gratuit) installé dessus, ou Debian.
- Internet **pour l'installation seulement**. Ensuite, Jarvis marche aussi hors ligne.
- Ton iPhone, pour les réglages de la fin.

## 1. Préparer Ubuntu
Ouvre un terminal et tape :
```bash
sudo apt update && sudo apt install -y git curl python3
```

## 2. Récupérer le code de Jarvis
```bash
git clone -b personal-agent https://github.com/4mqrcjjbm2-dev/bbench-mark ~/bbench-mark
cd ~/bbench-mark/personal-agent
```

## 3. (Optionnel) Connecter GitHub pour ton Cerveau
Ton dépôt `cerveaux-` est privé. Pour que Jarvis s'en serve, connecte GitHub une fois :
```bash
sudo apt install -y gh && gh auth login
```

## 4. Tout installer en une commande
```bash
./deploy/installer-serveur.sh
```
Ce script fait tout :
1. il installe Docker ;
2. il génère ton **jeton secret**. **Note-le** : c'est le mot de passe de ta page Jarvis ;
3. il choisit le modèle d'IA selon la mémoire de la machine ;
4. il propose de cloner ton Cerveau ;
5. il lance Jarvis, Ollama et SearXNG, puis télécharge le modèle ;
6. il affiche le diagnostic.

Pour imposer un modèle : `./deploy/installer-serveur.sh qwen3:14b`.

## 5. Vérifier
```bash
./deploy/verifier.sh
```
Chaque ligne ✘ donne la commande pour régler le problème. Dans la page Jarvis, **Connexions → État du serveur** montre aussi la mémoire, le disque, la vitesse réelle du modèle et le modèle conseillé.

## 6. (Optionnel) Wikipédia hors ligne
```bash
./deploy/telecharger-savoir.sh moyen              # Wikipédia française, sans images
./deploy/telecharger-savoir.sh moyen wiktionnaire # + le Wiktionnaire
```
Le script affiche la taille avant de télécharger. Si la connexion coupe, relance-le : il reprend là où il s'était arrêté.

## 7. (Optionnel) Modèle renfort
Pour les grosses créations, un gros modèle cloud d'Ollama. Il peut coûter des crédits selon ton abonnement Ollama. Dans `.env` :
```
AGENT_MODELE_RENFORT=kimi-k3:cloud
```
puis :
```bash
docker compose exec ollama ollama signin
docker compose up -d jarvis
```

## 8. Brancher l'iPhone
1. Installe **Tailscale** sur le serveur (`curl -fsSL https://tailscale.com/install.sh | sh`, puis `sudo tailscale up` et `sudo tailscale serve --bg 8787`) et sur l'iPhone (App Store), avec le même compte.
2. Sur l'iPhone, ouvre l'adresse `https://…ts.net` dans Safari, entre ton jeton, puis **Partager → Sur l'écran d'accueil**.
3. **Notifications** : installe l'app **ntfy**, touche **+**, puis colle le sujet affiché dans **Connexions → Clés API**.
4. **Voix** : crée les raccourcis **Cortana** et **Caro** (voir le README, section 3), puis associe-les aux phrases « Cortana » et « Caro » dans **Réglages → Accessibilité → Raccourcis vocaux**.
5. **Wikipédia sur le téléphone, même sans serveur** : l'app **Kiwix**.

## 9. Claude Code sur l'ordinateur (optionnel)
```bash
./deploy/claude-local.sh             # modèle renfort s'il est configuré, sinon le modèle principal
./deploy/claude-local.sh qwen3:14b   # ou un modèle précis
```
Claude Code s'ouvre dans ton Cerveau, avec accès au code de Jarvis, et passe par Ollama. Avec un modèle local, c'est gratuit et ça marche même hors ligne. Pour le code, les petits modèles sont limités : pour un gros chantier, utilise le renfort.

## 10. Jarvis qui s'améliore lui-même
Demande à Cortana : « Améliore Jarvis pour… ». Elle lit son propre code et propose un changement. Tu le retrouves dans **Atelier**, avec le différentiel :
- **Tester et appliquer** : tous les tests tournent sur une copie. Si un seul échoue, rien ne change. Sinon, Jarvis fait une sauvegarde, applique le changement et redémarre.
- **Annuler cette évolution** : la version précédente revient.

Ces changements sont enregistrés en local (commit git). Pour les envoyer sur GitHub, où les voient la mise à jour du dimanche et Claude :
```bash
cd ~/bbench-mark && git push origin personal-agent
git -C ~/cerveaux- push    # la mémoire écrite par Jarvis
```

## Problèmes courants
| Symptôme | Solution |
|---|---|
| La page ne s'ouvre pas | `docker compose ps` puis `docker compose logs --tail 50 jarvis` |
| « Jeton refusé » | Le jeton est dans `.env` : `grep AGENT_TOKEN .env` |
| Réponses très lentes | Écran « État du serveur » : prends le modèle conseillé (`AGENT_MODEL=` dans `.env`, puis `docker compose up -d jarvis`) |
| « Modèle absent » | `docker compose exec ollama ollama pull <modèle>` |
| La recherche web ne marche pas | `docker compose restart searxng` ; sans Internet, c'est normal : Jarvis passe en mode hors ligne |
| Plus de place sur le disque | Les modèles et Wikipédia prennent beaucoup de place : `docker compose exec ollama ollama rm <modèle>` pour en retirer un |
| Mettre Jarvis à jour | `git pull` puis `docker compose up -d --build` |
