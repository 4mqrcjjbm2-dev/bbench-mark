# Mises à jour de Jarvis

Chaque évolution, la plus récente en haut : ce qui change, pourquoi, et comment c'est vérifié.
Les propositions en attente sont dans le Cerveau : `cerveaux-/memoire/a-faire.md`, section « Évolutions proposées ».

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
