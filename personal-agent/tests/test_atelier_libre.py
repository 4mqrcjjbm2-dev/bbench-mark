"""L'atelier (vrais fichiers), les autorisations, la recherche web libre et le moteur Ollama."""

from __future__ import annotations

import json
import zipfile

import httpx
import pytest

from agent.atelier import Atelier, AtelierErreur
from agent.storage import JsonStore
from agent.tools import ToolContext, run_tool


@pytest.fixture
def ctx(tmp_path):
    store = JsonStore(tmp_path / "data")
    return ToolContext(store, "Europe/Paris", atelier=Atelier(tmp_path / "atelier", store))


def test_document_word_pdf_md(ctx):
    contenu = "# Expérience\n- Cariste, 3 ans\n1. Permis classe 5\nJe suis **fiable** et ponctuel. Prix : 25 €"
    for fmt, ext in (("docx", ".docx"), ("pdf", ".pdf"), ("md", ".md")):
        out, err = run_tool(ctx, "creer_document", {"nom": "CV Émond", "titre": "Curriculum vitæ", "contenu": contenu,
                                                    "format": fmt})
        assert not err, out
        p = ctx.atelier.racine / "documents" / f"CV-Émond{ext}"
        assert p.is_file() and p.stat().st_size > 100
    with zipfile.ZipFile(ctx.atelier.racine / "documents" / "CV-Émond.docx") as z:
        xml = z.read("word/document.xml").decode()
    assert "fiable" in xml and "Cariste" in xml and "<w:b/>" in xml  # le gras est conservé
    assert (ctx.atelier.racine / "documents" / "CV-Émond.pdf").read_bytes()[:4] == b"%PDF"


def test_tableur_budget_avec_totaux(ctx):
    from openpyxl import load_workbook
    out, err = run_tool(ctx, "creer_tableur", {"nom": "Budget novembre", "feuilles": [
        {"nom": "Dépenses", "colonnes": ["Poste", "Montant"], "lignes": [["Loyer", 900], ["Épicerie", 350.5]],
         "totaux": True}]})
    assert not err, out
    ws = load_workbook(ctx.atelier.racine / "tableurs" / "Budget-novembre.xlsx")["Dépenses"]
    assert ws["A1"].value == "Poste" and ws["B3"].value == 350.5 and ws["B4"].value == "=SUM(B2:B3)"


def test_site_cree_et_verifie(ctx):
    bon = "<!doctype html><html><head><title>x</title></head><body><h1>Salut</h1></body></html>"
    out, err = run_tool(ctx, "creer_site", {"nom": "vitrine", "fichiers": {"index.html": bon, "style.css": "h1{}"}})
    assert not err and "/atelier/sites/vitrine/index.html" in out and "Problèmes" not in out
    out, _ = run_tool(ctx, "creer_site", {"nom": "casse", "fichiers": {"index.html": "<div><span>oups</div>"}})
    assert "Problèmes trouvés" in out and "doctype" in out  # l'agent reçoit de quoi se corriger


def test_verification_code_et_chemins(ctx):
    run_tool(ctx, "atelier_ecrire", {"chemin": "code/ok.py", "contenu": "print('salut')\n"})
    run_tool(ctx, "atelier_ecrire", {"chemin": "code/ko.py", "contenu": "def f(:\n"})
    assert json.loads(run_tool(ctx, "verifier_fichier", {"chemin": "code/ok.py"})[0])["ok"] is True
    ko = json.loads(run_tool(ctx, "verifier_fichier", {"chemin": "code/ko.py"})[0])
    assert ko["ok"] is False and "Ligne 1" in ko["erreur"]
    with pytest.raises(AtelierErreur):
        ctx.atelier.chemin("../../etc/passwd")


def test_rien_ne_s_execute_sans_autorisation(ctx, tmp_path):
    out, err = run_tool(ctx, "executer_commande", {"commande": "echo bonjour > preuve.txt", "raison": "test"})
    assert not err and "autorisation" in out
    assert not (ctx.atelier.racine / "preuve.txt").exists()  # rien n'a tourné
    hors = tmp_path / "ailleurs" / "note.txt"
    out, _ = run_tool(ctx, "atelier_ecrire", {"chemin": str(hors), "contenu": "x"})
    assert "hors de l'atelier" in out and not hors.exists()
    demandes = ctx.store.list_items("demandes")
    assert [d["statut"] for d in demandes] == ["en_attente", "en_attente"]
    res = ctx.atelier.executer_demande(demandes[0])  # ce que fait « Autoriser »
    assert res["code"] == 0 and (ctx.atelier.racine / "preuve.txt").read_text().strip() == "bonjour"


def test_caro_ne_cree_rien(tmp_path):
    store = JsonStore(tmp_path)
    c = ToolContext(store, "Europe/Paris", atelier=Atelier(tmp_path / "at", store), lecture_seule=True)
    for nom, args in (("creer_document", {"titre": "x", "contenu": "y"}),
                      ("executer_commande", {"commande": "ls", "raison": "r"})):
        out, err = run_tool(c, nom, args)
        assert err and "Cortana" in out
    assert store.list_items("demandes") == []


def test_recherche_libre_searxng_puis_duckduckgo(tmp_path):
    ddg = ('<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexemple.ca%2Fa&amp;rut=1">'
           'Titre <b>A</b></a><a class="result__snippet" href="x">Extrait &amp; info</a>')

    def handler(req):
        if "searx" in str(req.url):
            return httpx.Response(503)
        if "duckduckgo" in str(req.url):
            return httpx.Response(200, text=ddg)
        return httpx.Response(404)

    c = ToolContext(JsonStore(tmp_path), "Europe/Paris", http=httpx.Client(transport=httpx.MockTransport(handler)),
                    searxng_url="http://searx.local")
    res = json.loads(run_tool(c, "recherche_web", {"requete": "prix maison"})[0])
    assert res == [{"titre": "Titre A", "url": "https://exemple.ca/a", "extrait": "Extrait & info"}]


def test_lecture_page_et_protection_reseau_interne(tmp_path):
    from agent import web
    page = "<html><head><title>Météo</title><script>x()</script></head><body><nav>menu</nav><p>Il fait 5 °C</p></body></html>"
    texte = web.texte_de_page(page)
    assert texte.startswith("# Météo") and "5 °C" in texte and "x()" not in texte and "menu" not in texte
    c = ToolContext(JsonStore(tmp_path), "Europe/Paris")
    for url in ("http://127.0.0.1:8787/api/state", "http://localhost/", "file:///etc/passwd"):
        out, err = run_tool(c, "lire_page", {"url": url})
        assert err, url


def test_moteur_ollama(tmp_path, monkeypatch):
    """Avec Ollama : appel non-beta, sans paramètres propres à Claude, outils web libres inclus."""
    from anthropic.types import Message

    from agent.config import load_settings
    from agent.core import Agent
    from agent.llm import creer_client

    monkeypatch.setenv("AGENT_FOURNISSEUR", "ollama")
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    st = load_settings()
    assert st.model == "qwen3:8b" and str(creer_client(st).base_url).startswith("http://localhost:11434")

    class Fake:
        def __init__(self):
            self.calls = []
            self.messages = self

        def create(self, **kw):
            self.calls.append(kw)
            return Message.model_validate({"id": "m", "type": "message", "role": "assistant", "model": "qwen3:8b",
                                           "content": [{"type": "text", "text": "Salut !"}], "stop_reason": "end_turn",
                                           "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}})

    fake = Fake()
    assert Agent(st, client=fake).ask("salut").text == "Salut !"
    kw = fake.calls[0]
    assert isinstance(kw["system"], str) and "Cortana" in kw["system"]
    for absent in ("thinking", "output_config", "cache_control", "betas", "fallbacks"):
        assert absent not in kw
    noms = {t["name"] for t in kw["tools"]}
    assert {"recherche_web", "lire_page", "creer_document", "creer_site", "executer_commande"} <= noms
    assert not any(t.get("type", "").startswith("web_search") for t in kw["tools"])


def test_serveur_atelier_et_autorisations(tmp_path, monkeypatch):
    import time as _t

    from fastapi.testclient import TestClient

    from agent import server
    from agent.config import load_settings
    from agent.core import Agent

    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AGENT_ATELIER", str(tmp_path / "atelier"))
    server.settings = load_settings()
    server._agent = Agent(server.settings, client=object())
    a = server._agent
    a.atelier.ecrire("sites/demo/index.html", "<!doctype html><p>Salut</p>")
    d = a.atelier.demander("commande", {"commande": "echo ok > fait.txt", "dossier": ""}, "test")
    c = TestClient(server.app)
    H = {"Authorization": "Bearer " + "t" * 32}

    assert c.get("/atelier/sites/demo/index.html").status_code == 401  # pas de cookie : refusé
    assert c.post("/api/session", headers=H).status_code == 200
    r = c.get("/atelier/sites/demo/")
    assert r.status_code == 200 and "Salut" in r.text and r.headers["content-security-policy"].startswith("sandbox")
    assert c.get("/api/state").status_code == 401  # le cookie n'ouvre PAS l'API

    st = c.get("/api/state", headers=H).json()
    assert st["demandes"][0]["statut"] == "en_attente" and any(f["chemin"] == "sites/demo/index.html" for f in st["atelier"])
    assert not (a.atelier.racine / "fait.txt").exists()
    assert c.post(f"/api/demandes/{d['id']}/autoriser", headers=H).status_code == 200
    for _ in range(50):
        if a.store.list_items("demandes")[0]["statut"] != "en_cours":
            break
        _t.sleep(0.05)
    assert a.store.list_items("demandes")[0]["statut"] == "terminee"
    assert (a.atelier.racine / "fait.txt").read_text().strip() == "ok"
    assert c.post(f"/api/demandes/{d['id']}/autoriser", headers=H).status_code == 409  # pas deux fois
