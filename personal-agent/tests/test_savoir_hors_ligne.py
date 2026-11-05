"""Wikipédia hors ligne (Kiwix), mode hors ligne automatique, images SVG."""

from __future__ import annotations

import httpx

from agent.atelier import Atelier
from agent.storage import JsonStore
from agent.tools import ToolContext, run_tool

CATALOGUE = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Wikipédia</title><name>wikipedia_fr_all_nopic_2026-10</name><language>fra</language></entry>
<entry><title>Wikipedia</title><name>wikipedia_en_all_nopic_2026-09</name><language>eng</language></entry>
</feed>"""
RECHERCHE = """<html><body><div class="results"><ul>
<li><a href="/content/wikipedia_fr_all_nopic_2026-10/Montr%C3%A9al">Montréal</a>
<cite>Montréal est la plus grande ville du <b>Québec</b>.</cite><div class="book-title">Wikipédia</div></li>
<li><a href="/content/wikipedia_fr_all_nopic_2026-10/Charlevoix">Charlevoix</a><cite>Région du Québec.</cite></li>
</ul><a href="/search?pattern=x&start=25">suivant</a></div></body></html>"""
ARTICLE = "<html><head><title>Montréal</title></head><body><p>Montréal compte environ 1,8 million d'habitants.</p></body></html>"


def test_encyclopedie_hors_ligne(tmp_path):
    vus = []

    def handler(req):
        vus.append(str(req.url))
        u = str(req.url)
        if "/catalog/v2/entries" in u:
            return httpx.Response(200, text=CATALOGUE)
        if "/search" in u:
            assert req.url.params["books.name"] == "wikipedia_fr_all_nopic_2026-10"  # la bonne langue, nom exact
            return httpx.Response(200, text=RECHERCHE)
        if "/content/" in u:
            return httpx.Response(200, text=ARTICLE, headers={"content-type": "text/html"})
        return httpx.Response(404)

    c = ToolContext(JsonStore(tmp_path), "Europe/Paris", http=httpx.Client(transport=httpx.MockTransport(handler)),
                    kiwix_url="http://kiwix:8080")
    out, err = run_tool(c, "encyclopedie", {"requete": "Montréal"})
    assert not err, out
    assert out.startswith("[Wikipédia] Montréal") and "1,8 million" in out and "Charlevoix" in out
    assert any("/content/wikipedia_fr_all_nopic_2026-10/Montr%C3%A9al" in u for u in vus)

    sans = ToolContext(JsonStore(tmp_path), "Europe/Paris")
    out, err = run_tool(sans, "encyclopedie", {"requete": "x"})
    assert err and "Aucune encyclopédie" in out


def test_mode_hors_ligne_retire_les_outils_internet(tmp_path, monkeypatch):
    from agent.config import load_settings
    from agent.core import Agent

    monkeypatch.setenv("AGENT_FOURNISSEUR", "ollama")
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("KIWIX_URL", "http://kiwix:8080")
    monkeypatch.setenv("AGENT_HORS_LIGNE", "1")
    a = Agent(load_settings(), client=object())
    noms = {t["name"] for t in a.outils("cortana")}
    assert "encyclopedie" in noms and "creer_document" in noms and "creer_image_svg" in noms
    assert not noms & {"recherche_web", "prix_crypto", "backtest", "notifier", "consulter_specialiste"}
    monkeypatch.setenv("AGENT_HORS_LIGNE", "0")
    assert "recherche_web" in {t["name"] for t in a.outils("cortana")}
    monkeypatch.delenv("KIWIX_URL")
    b = Agent(load_settings(), client=object())
    assert "encyclopedie" not in {t["name"] for t in b.outils("cortana")}  # pas d'outil inutile décrit au modèle


def test_image_svg(tmp_path):
    store = JsonStore(tmp_path)
    c = ToolContext(store, "Europe/Paris", atelier=Atelier(tmp_path / "at", store))
    out, err = run_tool(c, "creer_image_svg", {"nom": "logo jarvis", "svg": '<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"/></svg>'})
    assert not err and "images/logo-jarvis.svg" in out
    assert 'xmlns="http://www.w3.org/2000/svg"' in (tmp_path / "at" / "images" / "logo-jarvis.svg").read_text()
    out, err = run_tool(c, "creer_image_svg", {"svg": "<svg><circle></svg>"})
    assert err and "SVG invalide" in out
