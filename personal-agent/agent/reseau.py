"""Mode hors ligne automatique : sans Internet, Jarvis retire les outils qui en ont besoin.

Moins d'erreurs, et moins de tokens (moins d'outils décrits au modèle). Vérifié au plus toutes les 2 minutes.
AGENT_HORS_LIGNE : "auto" (défaut), "1" (toujours hors ligne), "0" (toujours en ligne).
"""

from __future__ import annotations

import os
import threading
import time

import httpx

from . import etat

OUTILS_INTERNET = {"prix_crypto", "marche_crypto", "tendances_crypto", "marches_financiers", "matieres_premieres",
                   "analyse_technique", "backtest", "portefeuille_public", "notifier", "rapport_du_jour",
                   "recherche_web", "lire_page", "consulter_specialiste", "web_search", "web_fetch"}
_etat = {"quand": 0.0, "en_ligne": True}
_lock = threading.Lock()


def en_ligne(forcer: bool = False) -> bool:
    reglage = os.environ.get("AGENT_HORS_LIGNE", "auto").lower()
    if reglage in ("1", "oui", "true"):
        return False
    if reglage in ("0", "non", "false"):
        return True
    with _lock:
        if not forcer and time.time() - _etat["quand"] < 120:
            return _etat["en_ligne"]
    ok = False
    for url in ("https://duckduckgo.com", "https://www.wikipedia.org", "https://1.1.1.1"):
        try:
            httpx.head(url, timeout=3, follow_redirects=False)
            ok = True
            break
        except httpx.HTTPError:
            continue
    with _lock:
        _etat.update(quand=time.time(), en_ligne=ok)
    etat.signaler("internet", ok, "Connecté" if ok else "Hors ligne : outils Internet mis de côté")
    return ok
