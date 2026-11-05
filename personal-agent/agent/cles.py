"""Coffre à clés : les clés API se collent depuis la page et s'activent sans redémarrer.

Ordre de lecture : variable d'environnement (.env) puis coffre `data/cles.json` (permissions 600).
Une clé n'est jamais renvoyée en clair à la page : seulement « configurée » + ses 4 derniers caractères.
Ce qui peut être généré sans compte (le sujet de notifications ntfy) l'est automatiquement.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
from pathlib import Path

CLES = {
    "NTFY_TOPIC": {
        "nom": "Notifications iPhone (ntfy)", "agent": "beacon", "auto": True, "secret": False,
        "lien": "https://apps.apple.com/app/ntfy/id1625396347",
        "aide": "Généré automatiquement. Installe l'app ntfy, touche +, et abonne-toi à ce sujet.",
        "format": r"^[A-Za-z0-9_-]{8,64}$",
    },
    "ETHERSCAN_API_KEY": {
        "nom": "Etherscan", "agent": "orca", "auto": False, "secret": True,
        "lien": "https://etherscan.io/myapikey",
        "aide": "Compte gratuit sur etherscan.io → API Keys → Add. Débloque les portefeuilles Ethereum pour ORCA.",
        "format": r"^[A-Z0-9]{30,40}$",
    },
}

_lock = threading.Lock()


class Cles:
    def __init__(self, data_dir: Path) -> None:
        self.fichier = data_dir / "cles.json"

    def _lire(self) -> dict:
        try:
            return json.loads(self.fichier.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _ecrire(self, d: dict) -> None:
        self.fichier.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.fichier.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.fichier)

    def get(self, nom: str) -> str:
        return os.environ.get(nom) or self._lire().get(nom, "")

    def definir(self, nom: str, valeur: str) -> None:
        if nom not in CLES:
            raise ValueError("Clé inconnue.")
        valeur = valeur.strip()
        if not re.match(CLES[nom]["format"], valeur):
            raise ValueError(f"Format inattendu pour {CLES[nom]['nom']}. Vérifie que tu as copié la clé en entier.")
        with _lock:
            d = self._lire()
            d[nom] = valeur
            self._ecrire(d)

    def supprimer(self, nom: str) -> None:
        with _lock:
            d = self._lire()
            d.pop(nom, None)
            self._ecrire(d)

    def generer_auto(self) -> None:
        """Crée ce qui n'a besoin d'aucun compte (sujet ntfy long et impossible à deviner)."""
        if not self.get("NTFY_TOPIC"):
            with _lock:
                d = self._lire()
                d["NTFY_TOPIC"] = "jarvis-" + secrets.token_urlsafe(16).replace("_", "").replace("-", "")[:20]
                self._ecrire(d)

    def statut(self) -> list[dict]:
        out = []
        for nom, info in CLES.items():
            v = self.get(nom)
            out.append({
                "nom": nom, "titre": info["nom"], "agent": info["agent"], "lien": info["lien"], "aide": info["aide"],
                "configuree": bool(v), "auto": info["auto"],
                "source": "env" if os.environ.get(nom) else ("coffre" if v else ""),
                # Le sujet ntfy n'est pas un secret : il faut le voir pour s'y abonner.
                "apercu": (v if not info["secret"] else ("•••• " + v[-4:])) if v else "",
            })
        return out
