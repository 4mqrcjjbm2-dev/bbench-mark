"""Recherche et lecture web 100 % libres : SearXNG (auto-hébergé), DuckDuckGo en secours.

Avec Claude, Jarvis utilise la recherche web d'Anthropic ; avec un modèle libre (Ollama), ces deux
outils prennent le relais.
"""

from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
from urllib.parse import parse_qs, unquote, urlparse

from . import net

DDG = "https://html.duckduckgo.com/html/"
NAVIGATEUR = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Jarvis/1.0", "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.7"}


class WebErreur(Exception):
    pass


def _ddg(http, requete: str, n: int) -> list[dict]:
    texte = net.requete(http, "POST", DDG, service="duckduckgo", data={"q": requete, "kl": "ca-fr"},
                        headers=NAVIGATEUR).text
    out = []
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
                         r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', texte, re.S):
        url = m.group(1)
        if "uddg=" in url:  # lien de redirection DuckDuckGo → vraie adresse
            url = unquote(parse_qs(urlparse(url).query).get("uddg", [url])[0])
        out.append({"titre": _propre(m.group(2)), "url": url, "extrait": _propre(m.group(3))})
        if len(out) >= n:
            break
    return out


def _propre(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def rechercher(http, searxng_url: str, requete: str, n: int = 6) -> list[dict]:
    if searxng_url:
        try:
            d = net.get_json(http, f"{searxng_url}/search", service="searxng", ttl=300,
                             params={"q": requete, "format": "json", "language": "fr"})
            res = [{"titre": r.get("title", ""), "url": r.get("url", ""), "extrait": r.get("content", "")[:300]}
                   for r in d.get("results", [])[:n]]
            if res:
                return res
        except net.ServiceErreur:
            pass  # on bascule sur DuckDuckGo
    return _ddg(http, requete, n)


def _adresse_publique(url: str) -> None:
    """Refuse les adresses internes (protection SSRF : le serveur ne doit pas lire son propre réseau)."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise WebErreur("Adresse invalide : il faut une URL http(s).")
    try:
        for info in socket.getaddrinfo(p.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise WebErreur("Adresse interne refusée.")
    except socket.gaierror as e:
        raise WebErreur(f"Site introuvable : {p.hostname}") from e


def texte_de_page(source: str) -> str:
    source = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|form)[^>]*>.*?</\1>", " ", source)
    titre = re.search(r"(?is)<title[^>]*>(.*?)</title>", source)
    source = re.sub(r"(?i)<(br|/p|/div|/h\d|/li|/tr)[^>]*>", "\n", source)
    texte = html.unescape(re.sub(r"<[^>]+>", " ", source))
    texte = re.sub(r"[ \t\r\f\v]+", " ", texte)
    texte = re.sub(r"\n\s*\n+", "\n", texte).strip()
    return (f"# {_propre(titre.group(1))}\n" if titre else "") + texte


def lire(http, url: str, limite: int = 12000, verifier: bool = True) -> str:
    if verifier:
        _adresse_publique(url)
    r = net.requete(http, "GET", url, service="web", headers=NAVIGATEUR, follow_redirects=True)
    ctype = r.headers.get("content-type", "")
    if "json" in ctype:
        return json.dumps(r.json(), ensure_ascii=False)[:limite]
    if "html" not in ctype and "text" not in ctype:
        raise WebErreur(f"Type de contenu non lisible : {ctype or 'inconnu'}")
    return texte_de_page(r.text)[:limite]
