# Jarvis — agent personnel pour iPhone

Jarvis réunit sur une seule page : **la Blackbox** (la salle animée où l'on voit les agents travailler, avec le tableau des tâches en cours), **le Cerveau** (ta mémoire `cerveaux-`), **les backtests**, tes tâches et notes, et **toutes les connexions**.

Tu parles à Siri, ton agent Claude réfléchit, utilise ses outils, puis te répond à voix haute. Il peut aussi faire agir ton iPhone : créer un rappel, ouvrir un lien, copier un texte ou afficher une notification.

```
iPhone (Raccourci « Agent »)  ──HTTPS + jeton──▶  Serveur (ton Mac ou un VPS)  ──▶  API Claude
        ▲                                              │  outils : crypto, notes, tâches,
        └──────── réponse lue + action iPhone ◀────────┘  date/heure, recherche web
```

L'agent ne tourne pas sur l'iPhone lui-même : iOS ne permet pas de faire tourner un serveur en continu. Il tourne sur une machine allumée en permanence, et l'iPhone lui envoie les demandes.

## Ce que l'agent sait faire

| Demande (exemples) | Outil |
|---|---|
| « Prix du bitcoin et de l'ethereum ? » | `prix_crypto` (CoinGecko) |
| « Comment va le marché crypto ? » | `marche_crypto` |
| « Note : idée de wallet multi-signature » / « Lis mes notes » | `note_ajouter`, `notes_lister`, `note_supprimer` |
| « Ajoute la tâche : finir le graphique RSI » / « Mes tâches ? » | `tache_ajouter`, `taches_lister`, `tache_terminer` |
| « Rappelle-moi demain à 9 h d'acheter de l'ETH » | `action_iphone` → rappel iOS |
| « Ouvre le graphique BTC sur TradingView » | `action_iphone` → ouvrir une URL |
| « Quelles sont les actus sur le minage ? » | recherche web |
| « Nouvelle conversation » | remet la mémoire à zéro |

La conversation est mémorisée pendant 6 h (réglable). Les notes et les tâches sont stockées dans `data/`.

## 1. Installer le serveur (15 min)

Il faut une machine allumée en permanence : un Mac, un PC Linux, ou un petit VPS (environ 4 €/mois).

```bash
git clone <ton dépôt> && cd bbench-mark/personal-agent
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # → copie dans AGENT_TOKEN
nano .env                                                        # mets ta clé ANTHROPIC_API_KEY
./deploy/run.sh
```

Pour tester dans le terminal : `.venv/bin/python -m agent.cli "Quel est le prix du bitcoin ?"`

**Démarrage automatique :**
- Mac : `deploy/com.agent.personnel.plist` (les instructions sont dans le fichier)
- Linux / VPS : `deploy/agent-personnel.service`

## 2. Relier l'iPhone au serveur de façon sécurisée (Tailscale, gratuit)

N'ouvre pas le port 8787 sur Internet. Utilise plutôt **Tailscale**, un réseau privé entre tes appareils :

1. Installe Tailscale sur le serveur (tailscale.com/download) et sur l'iPhone (App Store), avec le même compte.
2. Sur le serveur, lance `tailscale serve --bg 8787`. Tailscale affiche une adresse HTTPS du type `https://mon-mac.tailXXXX.ts.net`.
3. Sur l'iPhone, active le VPN dans l'app Tailscale. L'agent n'est joignable que par tes appareils.

## 3. Créer le Raccourci sur l'iPhone 13

Dans l'app **Raccourcis**, appuie sur **+** et nomme le raccourci **Agent**. Ajoute ces actions dans l'ordre :

1. **Dicter le texte** (langue : français ; arrêt : après une pause).
2. **Obtenir le contenu de l'URL**
   - URL : `https://mon-mac.tailXXXX.ts.net/ask`
   - Méthode : **POST**
   - En-têtes : `Authorization` = `Bearer TON_AGENT_TOKEN`
   - Corps de requête : **JSON**, champ `text` (texte) = *Texte dicté*
3. **Obtenir la valeur du dictionnaire** : clé `reply` → **Énoncer le texte** (*Valeur du dictionnaire*).
4. **Obtenir la valeur du dictionnaire** : clé `action_type` (renomme la variable en *Action*), puis ajoute des blocs **Si** :
   - *Action* est `rappel` → **Ajouter un nouveau rappel** : titre = valeur de `action_texte`, alerte = valeur de `action_date`
   - *Action* est `ouvrir_url` → **Ouvrir les URL** : valeur de `action_url`
   - *Action* est `copier` → **Copier dans le presse-papiers** : valeur de `action_texte`
   - *Action* est `notification` → **Afficher la notification** : valeur de `action_texte`

Ensuite, dis simplement **« Dis Siri, Agent »**. Tu peux aussi ajouter le raccourci à l'écran d'accueil, ou à l'appui arrière (Réglages → Accessibilité → Toucher → Toucher le dos).

**Le lancer en disant « Cortana » (sans dire « Dis Siri ») :** sur iOS 18 et plus récent (l'iPhone 13 est compatible), va dans Réglages → Accessibilité → **Raccourcis vocaux** → Configurer → Exécuter un raccourci. Choisis **Agent**, puis enregistre la phrase « Cortana » en la prononçant 3 fois. Si le mot seul est mal reconnu, utilise une phrase plus longue, par exemple « Hé Cortana ». Ensuite, dis « Cortana », attends la dictée, puis donne ta demande. Il faut parler en deux temps : le mot déclencheur, puis la demande, pas d'une seule traite.

Pour écrire au lieu de parler, remplace l'étape 1 par **Demander une entrée**.

**Tâches automatiques :** dans Raccourcis → Automatisation, crée par exemple « Chaque jour à 8 h » → exécuter un raccourci qui envoie « Fais-moi le point du marché crypto et de mes tâches du jour ».

## 3 bis. Brancher le Cerveau (mémoire à long terme)

Sur la machine qui fait tourner Jarvis :

```bash
git clone https://github.com/<ton-compte>/cerveaux- ~/cerveaux-
cd ~/cerveaux- && git config user.name "Jarvis" && git config user.email "jarvis@local"
```

Puis, dans `.env` : `AGENT_CERVEAU_DIR=/Users/<toi>/cerveaux-` (chemin absolu). Pour pousser, la machine doit pouvoir faire `git push` sur ce dépôt : connexion GitHub déjà faite, clé SSH ou `gh auth login`.

Une fois branché, Jarvis :
- lit `doctrine.md`, `profil.md` et `lecons.md` avant chaque réponse (ces règles passent avant ses habitudes) ;
- peut lire n'importe quel fichier de `memoire/` (connaissances, prédictions, journal) ;
- écrit au **format exact** du dépôt : entrée de journal, nouvelle leçon `L-0XX`, ligne de prédiction « En attente » ;
- regroupe ses écritures dans un commit `jarvis: …`, fait `pull --rebase` puis `push origin main` en arrière-plan ;
- récupère toutes les 10 min ce qu'écrivent tes sessions Claude Code.

Il ne touche qu'au dossier `memoire/` (jamais aux compétences ni au `CLAUDE.md`).

## 4. La page Jarvis (sur l'iPhone ou l'ordinateur)

Ouvre `https://mon-mac.tailXXXX.ts.net/` dans Safari et entre ton `AGENT_TOKEN` (il reste enregistré sur l'appareil).

Pour l'avoir comme une app : bouton Partager → **Sur l'écran d'accueil**.

Une seule page au style Neurolab (`cerveaux-/design/systeme.md`), avec une barre pour sauter d'une section à l'autre :

| Section | Contenu |
|---|---|
| **Blackbox** | La salle des agents, animée : Jarvis au centre, six agents autour. Chaque fois qu'un agent travaille, sa station s'allume et des paquets de données partent du cœur vers lui. En dessous, le tableau de toutes les tâches (en cours d'abord), que l'on touche pour voir chaque étape, la réponse et l'action iPhone. Un champ permet de donner un ordre à Jarvis. |
| **Cerveau** | Leçons apprises, score des prédictions, dernier enregistrement git, doctrine, prédictions en attente, journal récent. |
| **Backtests** | Lancer un backtest (actif, stratégie, période, stop, frais) et voir le résultat, la comparaison avec « acheter et garder », la pire chute, le taux de réussite et la courbe du capital. |
| **Tâches & notes** | Ajouter, cocher, supprimer. Ce sont les mêmes que celles que gère Jarvis. |
| **Connexions** | État en direct : Claude, CoinGecko, recherche web, Cerveau (git), iPhone. |
| **Capacités** | Tout ce que Jarvis sait faire, avec des exemples sur lesquels appuyer pour les envoyer. |
| **Options** | Niveau de réflexion (low → max), recherche web on/off, configuration, nouvelle conversation. |
| **À venir** | Idées d'options à ajouter plus tard. Marque celles qui t'intéressent. |

**Les agents de la Blackbox** : chaque outil appartient à un agent spécialisé, et Jarvis les coordonne.

| Agent | Rôle | Outils |
|---|---|---|
| Analyste | Prix et marché crypto | `prix_crypto`, `marche_crypto` |
| Quant | Backtests | `backtest` |
| Archiviste | Mémoire du Cerveau | `memoire_lire`, `memoire_journal`, `memoire_lecon`, `memoire_prediction` |
| Éclaireur | Recherche web | `web_search`, `web_fetch` |
| Secrétaire | Tâches, notes, agenda | `tache_*`, `note_*`, `date_heure` |
| Opérateur | Actions sur l'iPhone | `action_iphone` |

La page se rafraîchit toutes les 1,5 s pendant qu'une tâche tourne, sinon toutes les 5 s. Si l'iPhone demande de réduire les animations, la salle reste fixe.

## Backtests : ce qu'ils font, et ce qu'ils ne font pas

- Trois stratégies : **tendance** (MM20/MM50), **croisement de moyennes** et **RSI**. Tu règles le stop-loss, les frais et la période (90 à 365 jours, en données quotidiennes CoinGecko).
- Pas de triche : le signal du jour J n'utilise que les données connues ce jour-là, et il est exécuté à la clôture du jour suivant.
- On rapporte toujours la **pire chute** et le **taux de réussite**, pas seulement le gain (leçon L-001 du Cerveau).
- **Jamais d'ordre réel**, aucun wallet, aucune clé d'échange. Le passé ne garantit pas le futur.

## Format de l'API

```http
POST /ask
Authorization: Bearer <AGENT_TOKEN>
{"text": "Prix du bitcoin ?", "session": "iphone"}

→ {"reply": "...", "action_type": "aucune|rappel|ouvrir_url|copier|notification",
   "action_texte": "", "action_url": "", "action_date": ""}
```

`GET /health` vérifie que le serveur tourne. `POST /reset` efface la conversation.
La page utilise `GET /api/state`, `POST /api/backtests`, `POST|DELETE /api/taches…`, `POST|DELETE /api/notes…` et `POST /api/options` (même jeton).

## Ajouter tes propres outils

Dans `agent/tools.py`, écris une fonction `mon_outil(ctx, args) -> str`, puis ajoute son schéma dans la liste `TOOLS`. Claude l'utilisera dès qu'une demande s'y prête. Par exemple : solde d'un wallet via Etherscan, alertes de prix, indicateurs RSI ou MACD, etc.

## Réglages (`.env`)

| Variable | Défaut | Rôle |
|---|---|---|
| `AGENT_MODEL` | `claude-opus-5-5` | Modèle Claude |
| `AGENT_EFFORT` | `low` | `low` répond vite (idéal à la voix) ; `medium` ou `high` pour des analyses plus poussées |
| `AGENT_SESSION_TTL_HOURS` | `6` | Durée de la mémoire de conversation |
| `AGENT_ENABLE_WEB` | `1` | Recherche web (facturée en plus par Anthropic) |
| `AGENT_FALLBACKS` | `1` | Si une demande légitime est refusée par erreur, elle est relancée sur un modèle de secours |
| `AGENT_TIMEZONE` | `Europe/Paris` | Fuseau horaire pour les dates et les rappels |
| `AGENT_CERVEAU_DIR` | *(vide)* | Chemin de ta copie locale de `cerveaux-` (active la mémoire) |
| `AGENT_CERVEAU_PUSH` | `1` | `0` = Jarvis fait seulement des commits locaux, sans push |

## Sécurité

- Garde `AGENT_TOKEN` secret : quiconque le possède peut parler à ton agent et consommer ta clé API.
- L'agent n'a **aucun** accès à des fonds : il lit des prix publics, il ne signe ni n'envoie aucune transaction, et les backtests sont des simulations.
- La page charge ses polices depuis Google Fonts. Sans Internet, elle utilise les polices du système.
- Les réponses finance sont informatives. L'agent ne donne pas de conseil d'achat ou de vente.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest -q
```
