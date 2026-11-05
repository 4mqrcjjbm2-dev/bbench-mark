"""L'écosystème Jarvis : les deux voix (Cortana, Caro) et les agents du Catalogue.

Source officielle des agents : le document « Catalogue des agents IA — Écosystème Cybertrash »
(https://claude.ai/artifact/BL29NXrEQgE6bRiAY9vN1y). Les statuts ci-dessous recopient ceux du
catalogue ; « outils » liste ce que l'agent fait VRAIMENT dans Jarvis aujourd'hui (vide = pas encore
branché). Pour mettre à jour un agent, modifie d'abord le catalogue, puis ce fichier.
"""

from __future__ import annotations

# --- Les deux voix -----------------------------------------------------------------------
PERSONAS = {
    "cortana": {
        "id": "cortana", "nom": "Cortana", "couleur": "#1ce6d7",
        "role": "Exécute les tâches avec l'application",
        "declencheur": "Dire « Cortana » (Raccourci vocal iOS)",
        # Cortana fait le travail elle-même pour ce qui n'a pas d'agent spécialisé.
        "outils": ["note_ajouter", "notes_lister", "note_supprimer", "tache_ajouter", "taches_lister",
                   "tache_terminer", "date_heure", "action_iphone"],
    },
    "caro": {
        "id": "caro", "nom": "Caro", "couleur": "#b26bff",
        "role": "La voix qui explique l'application",
        "declencheur": "« Dis Siri, Caro » ou dire « Caro » (Raccourci vocal iOS)",
        "outils": [],
    },
}

# Caro explique et consulte, elle ne modifie rien : voici les seuls outils qu'elle reçoit.
OUTILS_LECTURE = {"prix_crypto", "marche_crypto", "notes_lister", "taches_lister", "date_heure",
                  "memoire_lire", "agents_catalogue", "web_search", "web_fetch", "tendances_crypto",
                  "marches_financiers", "matieres_premieres", "analyse_technique", "portefeuille_public",
                  "rapport_du_jour", "consulter_specialiste"}

# --- Groupes (couleurs Neurolab) -------------------------------------------------------------
GROUPES = {
    "chefs": {"nom": "Chefs d'équipe", "couleur": "#1ce6d7"},
    "voix": {"nom": "Voix", "couleur": "#b26bff"},
    "jarvis": {"nom": "Produits Jarvis", "couleur": "#4da3ff"},
    "trading": {"nom": "Trading", "couleur": "#ffe14d"},
    "eclaireurs": {"nom": "Éclaireurs", "couleur": "#c6ff4d"},
    "analyse": {"nom": "Analyse", "couleur": "#7dd3fc"},
    "commerce": {"nom": "Commerce et pub", "couleur": "#ff9f43"},
    "setup": {"nom": "Setup", "couleur": "#f472b6"},
    "protection": {"nom": "Protection", "couleur": "#ff5c7a"},
}

# statut : "livre" | "test" | "partiel" | "a_batir"  (repris du catalogue)
CATALOGUE = [
    {"id": "nexus", "num": 6, "nom": "NEXUS", "court": "NEXUS", "groupe": "chefs",
     "role": "Chef d'orchestre de l'équipe",
     "fait": "Distribue les tâches, fait parler les agents ensemble et rassemble leurs résultats au même endroit.",
     "statut": "a_batir", "statut_txt": "À bâtir",
     "outils": ["memoire_lire", "memoire_journal", "memoire_lecon", "memoire_prediction", "agents_catalogue"],
     "dans_jarvis": "Tient la mémoire du Cerveau et la liste des agents."},
    {"id": "beacon", "num": 7, "nom": "BEACON", "court": "BEACON", "groupe": "chefs",
     "role": "Centrale des notifications et des signaux",
     "fait": "Rapport du matin (crypto, baleines, tendances, marchés) et alerte immédiate sur un signal important.",
     "statut": "a_batir", "statut_txt": "À bâtir", "outils": ["notifier", "rapport_du_jour"],
     "dans_jarvis": "Notifications sur l'iPhone (ntfy, sujet généré tout seul) et rapport du matin à l'heure choisie."},
    {"id": "vox", "num": 8, "nom": "VOX", "court": "VOX", "groupe": "voix",
     "role": "Traducteur du parler québécois",
     "fait": "Comprend les expressions de Charlevoix, du Saguenay et de la Côte-Nord jusqu'à Blanc-Sablon.",
     "statut": "a_batir", "statut_txt": "Conçu (lexique de base monté)", "outils": [], "integre": True,
     "dans_jarvis": "Intégré aux deux voix : Cortana et Caro comprennent le parler québécois (lexique à grossir)."},
    {"id": "jarvis_iphone", "num": 2, "nom": "JARVIS iPhone", "court": "J-IPHONE", "groupe": "jarvis",
     "role": "Agent personnel crypto et recherche",
     "fait": "Prix crypto, top du marché, recherche de tokens Solana, widget d'écran d'accueil.",
     "statut": "livre", "statut_txt": "Livré, tests à finir", "outils": []},
    {"id": "terminal", "num": 3, "nom": "Terminal JARVIS", "court": "TERMINAL", "groupe": "jarvis",
     "role": "Centre de commande IA style cyberpunk",
     "fait": "Discussion avec l'IA en français, historique, s'installe comme une app sur le téléphone.",
     "statut": "livre", "statut_txt": "Livré", "outils": []},
    {"id": "sniper", "num": 5, "nom": "Sniper Pro", "court": "SNIPER", "groupe": "trading",
     "role": "Chasseur de signaux de trading",
     "fait": "Repère des entrées sur BTC, SOL et ETH, avec stop et profit calculés. À mesurer par backtest.",
     "statut": "test", "statut_txt": "En test", "outils": ["analyse_technique"],
     "dans_jarvis": "Lecture technique MM20/50, RSI, MACD, Bollinger et score sur 5. Description, jamais un ordre."},
    {"id": "sol_paper", "num": 4, "nom": "SOL Paper Trader", "court": "SOL PAPER", "groupe": "trading",
     "role": "Entraîneur de trading sans risque",
     "fait": "Trade en argent virtuel, compte les frais, s'arrête après une perte max, note chaque trade.",
     "statut": "livre", "statut_txt": "Livré (simulation)", "outils": ["backtest"],
     "dans_jarvis": "Lance les backtests de la page (simulation uniquement)."},
    {"id": "swarm", "num": 10, "nom": "Swarm Alpha, Beta, Gamma", "court": "SWARM", "groupe": "trading",
     "role": "Trois bots de trading autonomes sur Solana",
     "fait": "Se partageraient l'analyse et l'exécution. Backtest et paper trading obligatoires avant tout réel.",
     "statut": "a_batir", "statut_txt": "Conçu, après l'achat des machines", "outils": []},
    {"id": "tao", "num": None, "nom": "TAO Staking", "court": "TAO", "groupe": "trading",
     "role": "Revenu passif sur Bittensor (bundle à part)",
     "fait": "Suit la balance et les récompenses de staking TAO et notifie le téléphone. Aucun rendement promis.",
     "statut": "partiel", "statut_txt": "Suivi livré, staking à bâtir", "outils": []},
    {"id": "echo", "num": 13, "nom": "ECHO", "court": "ECHO", "groupe": "eclaireurs",
     "role": "Radar des tendances sur les réseaux sociaux",
     "fait": "Suit ce qui monte sur TikTok et Instagram : sujets, produits, hashtags.",
     "statut": "a_batir", "statut_txt": "À bâtir", "outils": ["consulter_specialiste"],
     "dans_jarvis": "Veille des tendances réseaux sociaux par recherche web."},
    {"id": "pulse", "num": 14, "nom": "PULSE", "court": "PULSE", "groupe": "eclaireurs",
     "role": "Surveillant du marché crypto",
     "fait": "Suit le marché et repère les cryptos qui montent.",
     "statut": "a_batir", "statut_txt": "À bâtir", "outils": ["prix_crypto", "marche_crypto", "tendances_crypto"],
     "dans_jarvis": "Prix (CoinGecko, secours Coinbase), état du marché, cryptos tendance et plus fortes hausses/baisses."},
    {"id": "ledger", "num": 15, "nom": "LEDGER", "court": "LEDGER", "groupe": "eclaireurs",
     "role": "Analyste des finances et des marchés",
     "fait": "Suit les marchés financiers et les nouvelles économiques, en langage simple.",
     "statut": "a_batir", "statut_txt": "À bâtir", "outils": ["marches_financiers"],
     "dans_jarvis": "S&P 500, Nasdaq, Dow Jones et taux USD/CAD, USD/EUR (Stooq, Frankfurter, sans clé)."},
    {"id": "orca", "num": 16, "nom": "ORCA", "court": "ORCA", "groupe": "eclaireurs",
     "role": "Chasseur de baleines crypto",
     "fait": "Surveille les portefeuilles publics des gros joueurs et alerte. Alertes seulement, aucune copie de trade.",
     "statut": "a_batir", "statut_txt": "À bâtir", "outils": ["portefeuille_public"],
     "dans_jarvis": "Adresses publiques Bitcoin sans clé (mempool.space) ; Ethereum avec la clé Etherscan.",
     "cle": "ETHERSCAN_API_KEY"},
    {"id": "vault", "num": 21, "nom": "VAULT", "court": "VAULT", "groupe": "eclaireurs",
     "role": "Surveillant des actifs classiques",
     "fait": "Suit l'or, l'argent, le gaz et le pétrole, et alerte quand les prix bougent.",
     "statut": "a_batir", "statut_txt": "À bâtir", "outils": ["matieres_premieres"],
     "dans_jarvis": "Or, argent, pétrole WTI et gaz naturel (Stooq, sans clé)."},
    {"id": "prism", "num": 9, "nom": "PRISM", "court": "PRISM", "groupe": "analyse",
     "role": "Analyste",
     "fait": "Décompose une info compliquée (marché, nouvelle, document) en morceaux clairs.",
     "statut": "a_batir", "statut_txt": "Conçu, rôle à confirmer", "outils": ["web_search", "web_fetch", "consulter_specialiste"],
     "dans_jarvis": "Recherche et lecture web, et décompose une info compliquée en points clairs."},
    {"id": "silk", "num": 17, "nom": "SILK", "court": "SILK", "groupe": "commerce",
     "role": "Chasseur de tendances mode",
     "fait": "Repère les nouveaux styles de linge et ce qui commence à se vendre.",
     "statut": "a_batir", "statut_txt": "À bâtir", "outils": ["consulter_specialiste"],
     "dans_jarvis": "Veille mode par recherche web."},
    {"id": "aura", "num": 18, "nom": "AURA", "court": "AURA", "groupe": "commerce",
     "role": "Chasseuse de tendances beauté",
     "fait": "Suit les cosmétiques et les parfums qui montent.",
     "statut": "a_batir", "statut_txt": "À bâtir", "outils": ["consulter_specialiste"],
     "dans_jarvis": "Veille beauté par recherche web."},
    {"id": "festa", "num": 19, "nom": "FESTA", "court": "FESTA", "groupe": "commerce",
     "role": "Calendrier des fêtes et des saisons",
     "fait": "Prévoit les tendances d'Halloween, de Noël et des autres fêtes, des semaines d'avance.",
     "statut": "a_batir", "statut_txt": "À bâtir", "outils": ["consulter_specialiste"],
     "dans_jarvis": "Calendrier des fêtes et de ce qui va se vendre, par recherche web."},
    {"id": "forge", "num": 20, "nom": "FORGE", "court": "FORGE", "groupe": "commerce",
     "role": "Coach des nouvelles compagnies",
     "fait": "Aide les débutants à se lancer : produits faciles à vendre et quoi faire pour grandir.",
     "statut": "a_batir", "statut_txt": "À bâtir", "outils": ["consulter_specialiste"],
     "dans_jarvis": "Coach pour lancer une compagnie au Québec et au Canada."},
    {"id": "pub", "num": 12, "nom": "Agent Pub", "court": "PUB", "groupe": "commerce",
     "role": "Publicitaire automatique",
     "fait": "Publie tes annonces sur les réseaux à heures fixes.",
     "statut": "a_batir", "statut_txt": "Conçu", "outils": ["consulter_specialiste"],
     "dans_jarvis": "Rédige les annonces ; la publication reste à toi."},
    {"id": "rig", "num": 22, "nom": "RIG", "court": "RIG", "groupe": "setup",
     "role": "Technicien gaming",
     "fait": "Optimise les PC de jeu (performance, stockage, réglages) et suggère des setups selon le budget.",
     "statut": "a_batir", "statut_txt": "À bâtir", "outils": ["consulter_specialiste"],
     "dans_jarvis": "Optimisation de PC gaming, étape par étape."},
    {"id": "neon", "num": 23, "nom": "NEON", "court": "NEON", "groupe": "setup",
     "role": "Designer d'espace cyber-tech",
     "fait": "Suit les tendances déco : LED, affiches numériques, accessoires de setup.",
     "statut": "a_batir", "statut_txt": "À bâtir", "outils": ["consulter_specialiste"],
     "dans_jarvis": "Idées de setup et de déco cyber-tech avec budget."},
    {"id": "gardiens", "num": 11, "nom": "Gardiens (2 agents)", "court": "GARDIENS", "groupe": "protection",
     "role": "Protecteurs de tes données",
     "fait": "S'assurent que les données du téléphone ne sortent jamais du téléphone.",
     "statut": "a_batir", "statut_txt": "Conçu", "outils": []},
    {"id": "aegis", "num": 24, "nom": "AEGIS", "court": "AEGIS", "groupe": "protection",
     "role": "Garde du corps numérique",
     "fait": "Checkup des appareils, explique les risques simplement et montre comment se protéger.",
     "statut": "partiel", "statut_txt": "6 outils livrés, agent à bâtir", "outils": ["consulter_specialiste"],
     "dans_jarvis": "Checkup de sécurité guidé, en mots simples."},
]

# CARO est au catalogue (n° 1), mais dans Jarvis elle est l'une des deux voix, au centre de la salle.
CARO_CATALOGUE = {
    "num": 1, "nom": "CARO", "role": "Assistante vocale québécoise",
    "fait": "Répond à la voix, rappels et agenda, prix crypto, recherche web.",
    "statut_txt": "Livrée, finition en cours",
}

# Un outil partagé (consulter_specialiste) est attribué à l'agent choisi dans l'appel (voir core.agent_de).
AGENT_PAR_OUTIL = {o: a["id"] for a in CATALOGUE for o in a["outils"] if o != "consulter_specialiste"}
AGENT_PAR_OUTIL.update({o: "cortana" for o in PERSONAS["cortana"]["outils"]})


def agents_pour_page(cles=None) -> list[dict]:
    out = []
    for a in CATALOGUE:
        manque = bool(a.get("cle") and cles is not None and not cles.get(a["cle"]))
        out.append({**a, "couleur": GROUPES[a["groupe"]]["couleur"], "groupe_nom": GROUPES[a["groupe"]]["nom"],
                    "branche": bool(a["outils"]) or bool(a.get("integre")), "cle_manquante": manque})
    return out


def resume_catalogue() -> str:
    """Texte compact pour l'outil agents_catalogue et le guide de Caro."""
    lignes = [f"- CARO (n° 1, voix) : {CARO_CATALOGUE['role']}. Statut : {CARO_CATALOGUE['statut_txt']}."]
    for a in sorted(CATALOGUE, key=lambda a: a["num"] or 99):
        branche = f" Dans Jarvis aujourd'hui : {a['dans_jarvis']}" if a.get("dans_jarvis") else \
            " Pas encore branché dans Jarvis."
        num = f"n° {a['num']}" if a["num"] else "bundle à part"
        lignes.append(f"- {a['nom']} ({num}, {GROUPES[a['groupe']]['nom']}) : {a['role']}. "
                      f"{a['fait']} Statut : {a['statut_txt']}.{branche}")
    return "\n".join(lignes)


GUIDE_APP = """JARVIS, c'est tout l'écosystème : le serveur, la page web, la Blackbox, le Cerveau et les agents.

Les deux voix :
- Cortana exécute les tâches avec l'application. On la lance en disant « Cortana » (Raccourci vocal iOS) \
ou en choisissant Cortana dans la page. Elle a tous les outils.
- Caro explique l'application : ce que fait chaque section, chaque agent, où en est chacun, comment faire. \
Elle consulte, mais ne modifie rien. Pour agir, on demande à Cortana.

La page Jarvis (une seule page, au style Neurolab) :
- Blackbox : la salle animée. Jarvis au centre, Cortana et Caro autour, et tous les agents du Catalogue en \
cercle. Un agent s'allume quand il travaille. En dessous, le tableau de toutes les tâches.
- Cerveau : la mémoire à long terme (dépôt cerveaux-) : doctrine, leçons, prédictions, journal.
- Backtests : tester une stratégie sur l'historique (tendance, croisement de moyennes, RSI). Simulation \
uniquement, jamais d'ordre réel. On rapporte toujours la pire chute.
- Tâches et notes, Connexions (Claude, CoinGecko, web, Cerveau, iPhone), Capacités, Options \
(niveau de réflexion, recherche web), À venir (idées pour plus tard).

Ce qui marche pour vrai aujourd'hui : PULSE (prix, marché, tendances crypto), LEDGER (bourses et devises), \
VAULT (or, argent, pétrole, gaz), Sniper Pro (lecture technique), SOL Paper Trader (backtests), ORCA \
(portefeuilles publics ; Ethereum demande une clé Etherscan), BEACON (notifications iPhone et rapport du matin), \
NEXUS (mémoire du Cerveau), PRISM (recherche web), les spécialistes ECHO, SILK, AURA, FESTA, FORGE, NEON, RIG, \
AEGIS et Agent Pub (chacun avec sa recherche web), VOX (parler québécois), et Cortana (tâches, notes, rappels, \
iPhone). Encore à bâtir : JARVIS iPhone et Terminal JARVIS (produits séparés), Swarm (aucun trading autonome \
sans tests), TAO Staking, Gardiens.
Clés API : elles se collent dans la page, section Connexions → Clés API, et s'activent tout de suite."""
