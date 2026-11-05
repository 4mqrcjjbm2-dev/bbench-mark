"""Registre de l'état des connexions (Claude, CoinGecko, mémoire git, iPhone...)."""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_etat: dict[str, dict] = {}


def signaler(service: str, ok: bool, detail: str = "") -> None:
    """Note le dernier résultat d'un service (appelé par les outils et la boucle agent)."""
    with _lock:
        e = _etat.setdefault(service, {"dernier_ok": None, "derniere_erreur": None, "detail": ""})
        now = time.time()
        if ok:
            e["dernier_ok"] = now
        else:
            e["derniere_erreur"] = now
        e["ok"] = ok
        e["detail"] = detail[:200]


def lire() -> dict[str, dict]:
    with _lock:
        return {k: dict(v) for k, v in _etat.items()}


def reinitialiser() -> None:
    with _lock:
        _etat.clear()
