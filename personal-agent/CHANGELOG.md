# Mises à jour de Jarvis

Chaque évolution, la plus récente en haut : ce qui change, pourquoi, et comment c'est vérifié.
Les propositions en attente sont dans le Cerveau : `cerveaux-/memoire/a-faire.md`, section « Évolutions proposées ».

## 2026-11-05 · Modèle renfort
- **`AGENT_MODELE_RENFORT`** (ex. `kimi-k3:cloud`) : un gros modèle cloud qui prend le relais seulement pour Cortana, en ligne. Il s'active automatiquement pour les grosses créations (site, appli, jeu, plan d'affaires, analyse complète, demande très longue) ou avec le bouton **RENFORT**. Le modèle local gratuit reste le moteur par défaut.
- Chaque tâche faite par le renfort porte un badge et le nom du modèle ; sa consommation est comptée à part (« Dont renfort (crédits) »). Options : renfort disponible oui/non, automatique oui/non.
- Vérifié : tests du choix du modèle (auto, forcé, Caro, hors ligne, désactivé).

## 2026-11-05 · Savoir hors ligne, mode hors ligne, images
- **Wikipédia hors ligne** (Kiwix, open source) : outil `encyclopedie`, qui cherche et renvoie directement le meilleur article en un seul appel (moins de tokens). Installation : `./deploy/telecharger-savoir.sh moyen` (Wikipédia française sans images, option Wiktionnaire).
- **Mode hors ligne automatique** (`AGENT_HORS_LIGNE=auto`) : sans Internet, les outils qui en ont besoin ne sont même plus décrits au modèle. Moins d'erreurs et moins de tokens. Un outil sans service installé (ex. encyclopédie sans Kiwix) n'est pas envoyé non plus.
- **Images SVG** (`creer_image_svg`) : logos, icônes, illustrations, animations ; vérifiées, hors ligne.
- Vérifié : 39 tests. Non testé : un vrai kiwix-serve et un vrai téléchargement (pas d'accès réseau ici).

## 2026-11-05 · Économies de tokens et d'énergie
- **Compteur de consommation** : tokens lus et écrits par tâche (dans le détail de chaque tâche) et total du jour (Options). C'est la base pour mesurer chaque optimisation.
- **Modèle léger** (`AGENT_MODELE_LEGER`, ex. `qwen3:4b`) pour Caro et les spécialistes ; Cortana garde le modèle principal pour créer et exécuter.
- **Historique borné avec Ollama** (`AGENT_HISTORIQUE_MAX`, 24 messages) : les longues conversations ne ralentissent plus tout. La coupure ne sépare jamais un appel d'outil de son résultat.
- **Ollama économe** : le modèle se décharge après 5 minutes sans demande, et une seule demande à la fois.
- Vérifié : 36 tests.

## 2026-11-05 · Méthode « meilleur chemin »
- Jarvis choisit le chemin le plus probable, garde un plan B, 3 essais au plus par approche, puis change de voie.

## 2026-11-05 · Jarvis libre
- Moteur IA open source (Ollama), recherche web libre (SearXNG + DuckDuckGo), Atelier de création (Word, PDF, Excel, sites, code), autorisations avant toute commande, installation Docker en une commande.

## 2026-11-05 · Agents du Catalogue
- 19 agents sur 24 branchés, coffre à clés, notifications et rapport du matin (BEACON), Cortana et Caro.
