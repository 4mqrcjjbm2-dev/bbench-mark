# Jarvis — agent personnel pour iPhone

## Jarvis libre : ton outil de création, 100 % open source et gratuit

Jarvis tourne **sur ton serveur**, avec des logiciels libres :
- **Ollama**, le moteur IA : des modèles libres comme Qwen 3 ou gpt-oss, sur ta machine, ou les modèles cloud gratuits d'Ollama ;
- **SearXNG**, la recherche web libre et privée, avec DuckDuckGo en secours ;
- **Jarvis**, le serveur et la page.

Claude reste possible en option, si un jour tu ajoutes une clé : `AGENT_FOURNISSEUR=anthropic`.

### Installer en une commande (serveur Linux, Ubuntu ou Debian)

```bash
git clone <ton dépôt> && cd bbench-mark/personal-agent
./deploy/installer-serveur.sh qwen3:8b       # ou qwen3:14b, gpt-oss:20b… selon la mémoire du serveur
```

Le script fait tout le reste :
- il installe Docker ;
- il génère ton jeton secret et celui de SearXNG ;
- il lance Jarvis, Ollama et SearXNG ;
- il télécharge le modèle ;
- il prépare l'accès depuis l'iPhone par Tailscale.

**Quel modèle choisir ?**

| Ton serveur | Modèle conseillé |
|---|---|
| 8 Go de mémoire, sans carte graphique | `qwen3:8b` : marche, mais lentement |
| 16 Go et plus | `qwen3:14b` |
| Carte graphique 16 à 24 Go | `qwen3:32b` ou `gpt-oss:20b` : rapide et bien meilleur |
| Petit serveur, mais tu veux la qualité | un modèle cloud gratuit d'Ollama (liste sur [ollama.com/search?c=cloud](https://ollama.com/search?c=cloud)), après `docker compose exec ollama ollama signin` |

Les petits modèles libres se trompent plus souvent que les grands. Si un résultat ne te convient pas, prends un modèle plus gros.

### Le Savoir hors ligne (Wikipédia sans Internet)

```bash
./deploy/telecharger-savoir.sh moyen              # Wikipédia française, articles complets sans images
./deploy/telecharger-savoir.sh moyen wiktionnaire # + le Wiktionnaire
```

Le script trouve la dernière version sur download.kiwix.org, affiche sa taille et la télécharge. Si la connexion coupe, relance-le : il reprend là où il s'était arrêté. Il démarre ensuite Kiwix (open source). Jarvis consulte alors l'encyclopédie **sans Internet**, avec l'outil `encyclopedie`.

**Sans Internet, Jarvis passe tout seul en mode hors ligne.** Il garde l'IA locale, l'Atelier, la mémoire et Wikipédia, et met de côté ce qui demande Internet.

Sur l'iPhone lui-même, l'app gratuite **Kiwix** lit les mêmes fichiers Wikipédia hors ligne, même sans le serveur.

### L'Atelier : ce que Jarvis crée pour vrai

Dis à Cortana « Crée mon CV en PDF », « Fais un budget Excel », « Crée un site pour mon garage » ou « Écris un script qui trie mes fichiers ». Elle fabrique le **vrai fichier** dans l'atelier (`./atelier` sur le serveur), et tu le retrouves dans la section **Atelier** de la page : ouvrir, télécharger, aperçu des sites, supprimer.

| Création | Outil | Résultat |
|---|---|---|
| Lettres, CV, guides | `creer_document` | Word (.docx), PDF, Markdown |
| Budgets, inventaires | `creer_tableur` | Excel (.xlsx), avec formules et totaux |
| Sites, applis web | `creer_site` | HTML, CSS et JS, vérifiés automatiquement, aperçu dans la page |
| Images, logos, animations | `creer_image_svg` | SVG vérifié, hors ligne |
| Code, scripts | `atelier_ecrire` puis `verifier_fichier` | Python, JS, JSON… vérifiés et corrigés jusqu'à ce que ça passe |
| Recherche | `recherche_web` puis `lire_page` | Sources lues et citées |

**Autocorrection :** après chaque création de code ou de site, Jarvis le vérifie et corrige ses erreurs. Si un outil échoue, il essaie un autre chemin. Quand tu le corriges, il note une leçon dans le Cerveau.

### Agir sur la machine : tout, avec ta confirmation

Toute **commande**, et tout fichier écrit **hors de l'atelier**, crée une **demande d'autorisation**. Rien ne s'exécute avant que tu touches **Autoriser** dans la page, section Atelier. Ensuite, le résultat s'affiche dans la page et arrive en notification sur l'iPhone. Avec Docker, les commandes tournent dans le conteneur de Jarvis, sur le dossier de l'atelier.

**Sécurité :**
- Les pages créées par l'IA s'ouvrent dans un **bac à sable** : elles ne peuvent ni lire ta session ni appeler l'API de Jarvis.
- Jarvis refuse de lire les adresses internes du réseau.
- Caro ne crée et n'exécute rien.

---

**Jarvis, c'est l'écosystème au complet.** On lui parle par deux voix :
- **Cortana exécute** les tâches avec l'application. Elle a tous les outils : crypto, backtests, mémoire, tâches, notes, rappels, actions iPhone.
- **Caro explique** l'application : les sections, les agents du Catalogue, ce qui est livré ou à bâtir. Elle consulte, mais ne modifie rien. Si on lui demande d'agir, elle renvoie vers Cortana, et un garde-fou dans le code bloque toute écriture.

Chaque voix a sa propre conversation. Dans la Blackbox, Jarvis est au centre, Cortana et Caro autour du cœur, et **les 24 agents du [Catalogue](https://claude.ai/artifact/BL29NXrEQgE6bRiAY9vN1y)** en cercle, regroupés et colorés par équipe. Un nœud plein veut dire livré, à moitié plein en test ou partiel, en pointillé à bâtir ; le point néon marque un agent branché pour vrai dans Jarvis. Touche un agent pour voir sa fiche. La liste vit dans `agent/catalogue.py`.

**19 agents sur 24 sont branchés**, chacun sur son chemin le plus fiable : une source gratuite sans clé d'abord, une source de secours si possible, des réessais automatiques et un cache court. Si une source tombe, la réponse donne ce qui marche au lieu d'échouer.

| Agent | Ce qu'il fait dans Jarvis | Source | Clé ? |
|---|---|---|---|
| PULSE | Prix, marché, tendances, plus fortes hausses et baisses | CoinGecko (secours : Coinbase) | Non |
| LEDGER | S&P 500, Nasdaq, Dow Jones, USD→CAD, USD→EUR | Stooq, Frankfurter | Non |
| VAULT | Or, argent, pétrole WTI, gaz naturel | Stooq | Non |
| Sniper Pro | Lecture technique MM20/50, RSI, MACD, Bollinger, score sur 5 | CoinGecko | Non |
| SOL Paper Trader | Backtests (simulation) | CoinGecko | Non |
| ORCA | Portefeuilles publics : Bitcoin / Ethereum | mempool.space / Etherscan | Non / **oui (gratuite)** |
| BEACON | Notifications iPhone et rapport du matin automatique | ntfy | **Générée toute seule** |
| NEXUS | Mémoire du Cerveau, liste des agents | dépôt `cerveaux-` | Non |
| PRISM | Recherche web, décomposer une info | recherche web Claude | Non |
| ECHO, SILK, AURA, FESTA, FORGE, NEON, RIG, AEGIS, Agent Pub | Chacun répond comme un sous-agent avec son métier et sa propre recherche web | Claude + web | Non |
| VOX | Parler québécois compris par les deux voix | intégré | Non |
| Cortana | Tâches, notes, rappels, actions iPhone | local | Non |

Encore à bâtir : JARVIS iPhone et Terminal JARVIS (produits séparés), Swarm (aucun trading autonome sans tests), TAO Staking, Gardiens.

**Clés API.** Je ne crée pas de compte et je ne récupère pas de clé à ta place, c'est la règle de sécurité. En revanche :
- ce qui n'a pas besoin de compte est généré automatiquement (ton sujet de notifications ntfy) ;
- une clé se colle dans la page (**Connexions → Clés API**) et s'active tout de suite, sans redémarrage ;
- elle est rangée dans `data/cles.json` (permissions 600) et ne s'affiche jamais en entier.

**Notifications iPhone (BEACON).** Installe l'app gratuite **ntfy**, touche **+** et abonne-toi au sujet affiché dans Connexions → Clés API. Le rapport du matin part tout seul à l'heure choisie dans Options (08:00 par défaut). Le bouton « Envoyer un rapport maintenant » permet de tester.

Jarvis réunit aussi sur la même page : **la Blackbox** (la salle animée où l'on voit les agents travailler, avec le tableau des tâches en cours), **le Cerveau** (ta mémoire `cerveaux-`), **les backtests**, tes tâches et notes, et **toutes les connexions**.

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

**Deux raccourcis, deux voix.** Duplique le raccourci : appelle le premier **Cortana**, le second **Caro**. Dans le corps JSON, ajoute le champ `persona` (texte) = `cortana` dans le premier et `caro` dans le second.

**Le lancer en disant « Cortana » (sans dire « Dis Siri ») :** sur iOS 18 et plus récent (l'iPhone 13 est compatible), va dans Réglages → Accessibilité → **Raccourcis vocaux** → Configurer → Exécuter un raccourci. Choisis **Agent**, puis enregistre la phrase « Cortana » en la prononçant 3 fois. Si le mot seul est mal reconnu, utilise une phrase plus longue, par exemple « Hé Cortana ». Ensuite, dis « Cortana », attends la dictée, puis donne ta demande. Fais la même chose avec la phrase « Caro » pour le raccourci Caro ; « Dis Siri, Caro » fonctionne aussi. Il faut parler en deux temps : le mot déclencheur, puis la demande, pas d'une seule traite.

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
{"text": "Prix du bitcoin ?", "session": "iphone", "persona": "cortana"}   // ou "caro"

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
