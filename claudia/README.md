# Claudia — ton agent IA personnel

Claudia tourne sur ton ordinateur et utilise l'API Claude (modèle `claude-opus-5-5`).
Tu lui parles depuis le terminal **ou depuis ton iPhone** avec l'app Raccourcis (et Siri).

Ce qu'elle sait faire aujourd'hui :

| Outil | Rôle |
|---|---|
| `memoriser` / `oublier` | Mémoire durable (fichier `memoire.json`), relue à chaque nouvelle conversation |
| `prix_crypto` | Cours en direct via CoinGecko (USD, CAD, variation 24 h) |
| `heure_actuelle` | Date et heure dans ton fuseau |
| recherche web | Actualité, infos récentes (exécutée par Anthropic) |

## 1. Installation (sur l'ordinateur)

```bash
cd bbench-mark/claudia
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Ouvre `.env` et remplis :
- `ANTHROPIC_API_KEY` : ta clé créée sur console.anthropic.com
- `CLAUDIA_JETON` : un mot de passe long, généré avec
  `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`

`.env` et `memoire.json` sont ignorés par git : ta clé ne part jamais sur GitHub.

## 2. Parler à Claudia dans le terminal

```bash
python3 claudia.py
```

## 3. Parler à Claudia depuis l'iPhone

**a) Lancer le serveur sur l'ordi**

```bash
python3 serveur.py        # écoute sur le port 8787
```

**b) Rendre l'ordi joignable depuis l'iPhone**
- **Même Wi-Fi** : trouve l'IP locale de l'ordi (ex. `192.168.1.42`).
  L'adresse sera `http://192.168.1.42:8787`.
- **Partout (4G, hors de chez toi)** : installe **Tailscale** (gratuit) sur l'ordi et
  l'iPhone, avec le même compte. Utilise l'adresse Tailscale de l'ordi (ex. `http://100.x.y.z:8787`).
  N'ouvre pas le port sur ta box Internet.

**c) Créer le raccourci « Claudia »** dans l'app Raccourcis :
1. **Demander une saisie** : texte, question « Que veux-tu demander à Claudia ? »
   (ou **Dicter le texte** pour parler).
2. **Obtenir le contenu de l'URL** :
   - URL : `http://<adresse-de-l-ordi>:8787/tache`
   - Méthode : **POST**
   - En-têtes : `Authorization` = `Bearer <ton CLAUDIA_JETON>`
   - Corps de requête : **JSON**, clé `texte` = *Saisie demandée*
3. **Obtenir la valeur du dictionnaire** : clé `reponse`.
4. **Afficher le résultat** (ou **Énoncer le texte** pour que Siri lise la réponse).

Dis ensuite « Dis Siri, Claudia » pour la lancer à la voix.

Pour garder le fil d'une conversation, ajoute la clé `conversation` dans le JSON
avec la valeur renvoyée par la réponse précédente.

## API du serveur

```
POST /tache
Authorization: Bearer <CLAUDIA_JETON>
{"texte": "Prix du bitcoin ?", "conversation": "optionnel"}

→ {"reponse": "...", "conversation": "a1b2..."}

GET /sante → {"ok": true}
```

## Réglages (`.env`)

| Variable | Défaut | Rôle |
|---|---|---|
| `CLAUDIA_MODELE` | `claude-opus-5-5` | Modèle Claude |
| `CLAUDIA_EFFORT` | `medium` | `low` = moins cher et plus rapide, `high` = plus réfléchi |
| `CLAUDIA_FUSEAU` | `America/Toronto` | Fuseau horaire |
| `CLAUDIA_PORT` | `8787` | Port du serveur |

## Ajouter un outil

Dans `claudia.py` :
1. écris une fonction Python, par ex. `outil_solde_wallet(adresse: str) -> str` ;
2. ajoute sa description à la liste `OUTILS` (nom, description, `input_schema`) ;
3. inscris-la dans le dictionnaire `OUTILS_LOCAUX`.

Claude décide seul quand l'appeler.
