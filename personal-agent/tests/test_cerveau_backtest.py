"""Tests du moteur de backtest et du lien avec la mémoire du Cerveau (hors-ligne)."""

from __future__ import annotations

import math
import os
import shutil
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("AGENT_TOKEN", "t" * 32)

from agent.backtest import BacktestErreur, Parametres, _rsi, executer  # noqa: E402
from agent.cerveau import Cerveau  # noqa: E402

JOUR = 86400


def serie(valeurs):
    return [(1_700_000_000 + i * JOUR, v) for i, v in enumerate(valeurs)]


def test_tendance_haussiere_gagne_et_rapporte_les_pertes():
    prix = serie([100 * 1.01 ** i for i in range(200)])
    r = executer(prix, Parametres("tendance"))
    assert r["rendement_pct"] > 0 and r["buy_hold_pct"] > r["rendement_pct"]  # entre en retard
    for cle in ("pire_chute_pct", "taux_reussite_pct", "nb_trades", "buy_hold_pire_chute_pct"):
        assert cle in r
    assert len(r["courbe"]) <= 80 and r["avertissement"]


def test_stop_loss_limite_la_chute():
    prix = serie([100 * 1.01 ** i for i in range(120)] + [100 * 1.01 ** 119 * 0.97 ** i for i in range(1, 80)])
    r = executer(prix, Parametres("tendance", stop_pct=5))
    assert r["pire_chute_pct"] > r["buy_hold_pire_chute_pct"]  # bien moins pire qu'acheter et garder
    assert r["pire_chute_pct"] > -15


def test_pas_de_vision_du_futur():
    """Changer les prix APRÈS le jour J ne doit pas changer la courbe jusqu'au jour J."""
    base = [100 + 10 * math.sin(i / 7) + i * 0.3 for i in range(200)]
    autre = base[:150] + [v * 0.5 for v in base[150:]]
    a = executer(serie(base), Parametres("croisement_mm"))
    b = executer(serie(autre), Parametres("croisement_mm"))
    # 80 points échantillonnés sur 200 jours : les ~55 premiers couvrent les jours < 140.
    assert a["courbe"][:55] == b["courbe"][:55]


def test_rsi_et_erreurs():
    vals = _rsi([float(i) for i in range(30)], 14)
    assert vals[14] == 100.0 and vals[13] is None
    with pytest.raises(BacktestErreur):
        executer(serie([1.0] * 30), Parametres())
    with pytest.raises(BacktestErreur):
        executer(serie([1.0 + i for i in range(100)]), Parametres("croisement_mm", rapide=30, lente=10))


@pytest.fixture
def cerveau(tmp_path):
    racine = tmp_path / "cerveaux"
    (racine / "memoire" / "journal").mkdir(parents=True)
    (racine / "memoire" / "doctrine.md").write_text("# Doctrine\n\n1. **Je creuse avant de déranger.** x\n")
    (racine / "memoire" / "profil.md").write_text("# Profil\n- iPhone 13\n")
    (racine / "memoire" / "lecons.md").write_text(
        "# Leçons\n\n```\n## L-001 · 2026-10-19 · catégorie\n- Règle : …\n```\n\n"
        "## L-001 · 2026-10-19 · trading\n- Ce qui s'est passé : a\n- Pourquoi : b\n- Règle : Toujours X.\n- Vu : 1 fois\n")
    (racine / "memoire" / "predictions.md").write_text(
        "# Prédictions\n\n## Score\n- Prédictions vérifiées : 0\n\n## En attente\n"
        "| Date | Actif | Prix au moment | Prédiction (24 h) | Raison | Échéance |\n|---|---|---|---|---|---|\n\n"
        "## Vérifiées\n| Date |\n|---|\n")
    if shutil.which("git"):
        subprocess.run(["git", "init", "-q", str(racine)], check=True)
        subprocess.run(["git", "-C", str(racine), "-c", "user.name=t", "-c", "user.email=t@t", "add", "."], check=True)
        subprocess.run(["git", "-C", str(racine), "-c", "user.name=t", "-c", "user.email=t@t",
                        "commit", "-qm", "init"], check=True)
        subprocess.run(["git", "-C", str(racine), "config", "user.name", "Jarvis"], check=True)
        subprocess.run(["git", "-C", str(racine), "config", "user.email", "jarvis@local"], check=True)
    return Cerveau(racine, pousser=False)


def test_cerveau_lit_et_ecrit_au_bon_format(cerveau):
    assert "Je creuse" in cerveau.contexte()
    assert cerveau.ajouter_lecon("voix", "a", "b", "Faire c.") == "Leçon L-002 ajoutée."
    cerveau.noter_journal("Backtest BTC", "tendance 1 an", "réussi")
    cerveau.enregistrer_prediction("BTC", "61 200 €", "hausse", "MM20 > MM50", "2026-11-06")
    cerveau.attendre()
    r = cerveau.resume()
    assert [l["id"] for l in r["lecons"]] == ["L-001", "L-002"]  # l'exemple du bloc de code est ignoré
    assert r["predictions_attente"][0]["actif"] == "BTC"
    assert r["journal"][0]["titre"] == "Backtest BTC"
    assert r["principes"] == ["Je creuse avant de déranger."]
    if cerveau.est_git:
        assert r["commit"]["message"].startswith("jarvis: leçon L-002 ; journal")
    with pytest.raises(Exception):
        cerveau.lire("../../etc/passwd")


def test_backtest_depuis_le_tableau_de_bord(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from agent import server, tools
    from agent.config import load_settings
    from agent.core import Agent

    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(tools, "recuperer_prix", lambda http, a, d, j: serie([100 * 1.01 ** i for i in range(j)]))
    server._agent = Agent(load_settings(), client=object())
    c = TestClient(server.app)
    H = {"Authorization": "Bearer " + "t" * 32}
    r = c.post("/api/backtests", json={"actif": "bitcoin", "strategie": "rsi", "jours": 180}, headers=H)
    assert r.status_code == 200 and r.json()["jours"] == 180
    st = c.get("/api/state", headers=H).json()
    assert st["backtests"][0]["actif"] == "bitcoin"
    assert st["activite"][0]["etapes"][0]["agent"] == "sol_paper"
    assert len(st["agents"]) == 24 and {p["id"] for p in st["personas"]} == {"cortana", "caro"}
    assert {"nexus", "pulse", "aegis", "rig", "neon", "tao"} <= {a["id"] for a in st["agents"]}
    assert {x["id"] for x in st["connexions"]} == {"claude", "coingecko", "web", "memoire", "iphone"}
    assert c.post("/api/backtests", json={"actif": "bitcoin", "jours": 30}, headers=H).status_code == 422
