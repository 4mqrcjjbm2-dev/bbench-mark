"""Le Savoir hors ligne : Wikipédia et d'autres encyclopédies servies par Kiwix (kiwix-serve), sans Internet.

- Catalogue OPDS (XML) : /catalog/v2/entries → nom exact des encyclopédies installées (le nom porte une date).
- Recherche plein texte : /search?pattern=…&books.name=… (HTML). books.name est exigé quand plusieurs
  langues sont installées. Réf. : https://kiwix-tools.readthedocs.io/en/latest/kiwix-serve.html
"""

from __future__ import annotations

import html
import re
from urllib.parse import urljoin

from . import net, web


class SavoirErreur(Exception):
    pass


def livres(http, base: str) -> list[dict]:
    xml = net.get_text(http, f"{base}/catalog/v2/entries", service="kiwix", ttl=600, params={"count": 200})
    out = []
    for e in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        nom = re.search(r"<name>(.*?)</name>", e)
        if not nom:
            continue
        titre = re.search(r"<title>(.*?)</title>", e)
        langue = re.search(r"<language>(.*?)</language>", e)
        out.append({"nom": nom.group(1).strip(), "titre": html.unescape(titre.group(1).strip()) if titre else nom.group(1),
                    "langue": langue.group(1).strip() if langue else ""})
    return out


def _resultats(page: str, base: str, livre: str, n: int) -> list[dict]:
    out = []
    for m in re.finditer(r'<a href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a href=|</ul>|$)', page, re.S):
        href = m.group(1)
        if "/search" in href or "/catalog" in href or "/skin" in href or href.startswith("http"):
            continue
        extrait = re.search(r"<cite>(.*?)</cite>", m.group(3), re.S)
        titre = web._propre(m.group(2))
        if not titre:
            continue
        out.append({"titre": titre, "url": urljoin(base + "/", href.lstrip("/")),
                    "extrait": web._propre(extrait.group(1))[:300] if extrait else "", "source": livre})
        if len(out) >= n:
            break
    return out


def chercher(http, base: str, requete: str, langue: str = "fra", n: int = 5) -> list[dict]:
    if not base:
        raise SavoirErreur("Aucune encyclopédie hors ligne n'est installée (KIWIX_URL vide).")
    tous = livres(http, base)
    if not tous:
        raise SavoirErreur("Kiwix répond mais aucune encyclopédie n'est installée : lance deploy/telecharger-savoir.sh.")
    choisis = [b for b in tous if langue in b["langue"]] or tous
    res: list[dict] = []
    for b in choisis[:3]:  # les 3 premières encyclopédies de la langue (Wikipédia, Wiktionnaire…)
        try:
            page = net.get_text(http, f"{base}/search", service="kiwix", ttl=300,
                                params={"pattern": requete, "books.name": b["nom"], "pageLength": n})
            res += _resultats(page, base, b["titre"], n)
        except net.ServiceErreur:
            continue
    return res


def lire(http, url: str, limite: int = 6000) -> str:
    texte = net.get_text(http, url, service="kiwix", ttl=3600)
    return web.texte_de_page(texte)[:limite]
