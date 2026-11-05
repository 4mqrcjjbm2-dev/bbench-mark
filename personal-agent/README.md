# Agent personnel pour iPhone

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

Pour écrire au lieu de parler, remplace l'étape 1 par **Demander une entrée**.

**Tâches automatiques :** dans Raccourcis → Automatisation, crée par exemple « Chaque jour à 8 h » → exécuter un raccourci qui envoie « Fais-moi le point du marché crypto et de mes tâches du jour ».

## Format de l'API

```http
POST /ask
Authorization: Bearer <AGENT_TOKEN>
{"text": "Prix du bitcoin ?", "session": "iphone"}

→ {"reply": "...", "action_type": "aucune|rappel|ouvrir_url|copier|notification",
   "action_texte": "", "action_url": "", "action_date": ""}
```

`GET /health` vérifie que le serveur tourne. `POST /reset` efface la conversation.

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

## Sécurité

- Garde `AGENT_TOKEN` secret : quiconque le possède peut parler à ton agent et consommer ta clé API.
- L'agent n'a **aucun** accès à des fonds : il lit des prix publics, il ne signe ni n'envoie aucune transaction.
- Les réponses finance sont informatives. L'agent ne donne pas de conseil d'achat ou de vente.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest -q
```
