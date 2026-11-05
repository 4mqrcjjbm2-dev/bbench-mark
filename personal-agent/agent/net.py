"""Requêtes HTTP fiables : réessais avec attente croissante, cache court, état des connexions.

But : qu'une demande marche du premier coup même si un service gratuit hoquette
(limite de débit 429, erreur 5xx, coupure réseau), sans jamais bloquer longtemps.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx

from . import etat

_cache: dict[tuple, tuple[float, Any]] = {}
_dormir = time.sleep  # remplaçable dans les tests
_lock = threading.Lock()
REESSAYABLE = {429, 500, 502, 503, 504}


class ServiceErreur(Exception):
    """Le service n'a pas répondu correctement malgré les réessais."""


def vider_cache() -> None:
    with _lock:
        _cache.clear()


def _cle(url: str, params: dict | None, fmt: str) -> tuple:
    return (url, tuple(sorted((params or {}).items())), fmt)


def requete(http: httpx.Client, method: str, url: str, *, service: str, params: dict | None = None,
            essais: int = 3, **kwargs) -> httpx.Response:
    derniere: Exception | None = None
    for i in range(essais):
        try:
            r = http.request(method, url, params=params, **kwargs)
            if r.status_code in REESSAYABLE and i < essais - 1:
                attente = float(r.headers.get("retry-after", 0) or 0) or 0.6 * (2 ** i)
                _dormir(min(attente, 4))
                continue
            if r.status_code >= 400:
                etat.signaler(service, False, f"HTTP {r.status_code}")
                raise ServiceErreur(f"{service} a répondu {r.status_code}.")
            etat.signaler(service, True, "Répond")
            return r
        except httpx.HTTPError as e:
            derniere = e
            if i < essais - 1:
                _dormir(0.6 * (2 ** i))
    etat.signaler(service, False, type(derniere).__name__ if derniere else "injoignable")
    raise ServiceErreur(f"{service} est injoignable pour l'instant.")


def get_json(http: httpx.Client, url: str, *, service: str, params: dict | None = None, ttl: float = 60,
             **kwargs) -> Any:
    cle = _cle(url, params, "json")
    with _lock:
        hit = _cache.get(cle)
    if ttl and hit and hit[0] > time.time():
        return hit[1]
    data = requete(http, "GET", url, service=service, params=params, **kwargs).json()
    if ttl:
        with _lock:
            _cache[cle] = (time.time() + ttl, data)
    return data


def get_text(http: httpx.Client, url: str, *, service: str, params: dict | None = None, ttl: float = 60,
             **kwargs) -> str:
    cle = _cle(url, params, "text")
    with _lock:
        hit = _cache.get(cle)
    if ttl and hit and hit[0] > time.time():
        return hit[1]
    text = requete(http, "GET", url, service=service, params=params, **kwargs).text
    if ttl:
        with _lock:
            _cache[cle] = (time.time() + ttl, text)
    return text
