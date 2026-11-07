"""Jarvis qui améliore son propre code : jamais sans autorisation, jamais avec un test rouge, toujours annulable."""

from __future__ import annotations

import subprocess

import pytest

from agent.evolution import Evolution, EvolutionErreur
from agent.storage import JsonStore
from agent.tools import ToolContext, run_tool


@pytest.fixture
def projet(tmp_path):
    """Un petit « Jarvis » séparé : son code, ses tests, un dépôt git."""
    src = tmp_path / "jarvis"
    (src / "agent").mkdir(parents=True)
    (src / "tests").mkdir()
    (src / "agent" / "__init__.py").write_text("")
    (src / "agent" / "calcul.py").write_text("def double(x):\n    return x * 2\n")
    (src / "tests" / "test_calcul.py").write_text(
        "from agent.calcul import double\n\ndef test_double():\n    assert double(3) == 6\n")
    subprocess.run(["git", "init", "-q", str(src)], check=True)
    subprocess.run(["git", "-C", str(src), "-c", "user.name=t", "-c", "user.email=t@t", "add", "."], check=True)
    subprocess.run(["git", "-C", str(src), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"], check=True)
    store = JsonStore(tmp_path / "data")
    return src, store, Evolution(src, store, tmp_path / "data")


def test_proposer_ne_change_rien(projet):
    src, store, evo = projet
    ctx = ToolContext(store, "Europe/Paris", evolution=evo)
    out, err = run_tool(ctx, "proposer_evolution", {"titre": "Triple", "raison": "test", "fichiers": {
        "agent/calcul.py": "def double(x):\n    return x * 2\n\ndef triple(x):\n    return x * 3\n"}})
    assert not err and "Rien n'est modifié" in out
    assert "triple" not in (src / "agent" / "calcul.py").read_text()
    d = store.list_items("demandes")[0]
    assert d["type"] == "evolution" and d["details"]["stats"]["agent/calcul.py"]["ajouts"] == 3
    assert "+def triple(x):" in d["details"]["diff"]
    assert "lignes 1-2 sur 2" in run_tool(ctx, "lire_code_jarvis", {"chemin": "agent/calcul.py"})[0]


def test_garde_fous_des_chemins(projet):
    src, store, evo = projet
    for rel in ("../ailleurs.py", "deploy/x.sh", "tests/test_calcul.py", ".env"):
        with pytest.raises(EvolutionErreur):
            evo.proposer("x", "y", {rel: "contenu"})
    with pytest.raises(EvolutionErreur):
        evo.proposer("x", "y", {"agent/calcul.py": (src / "agent" / "calcul.py").read_text()})  # identique
    caro = ToolContext(store, "Europe/Paris", evolution=evo, lecture_seule=True)
    out, err = run_tool(caro, "proposer_evolution", {"titre": "x", "raison": "y", "fichiers": {"agent/a.py": "x=1\n"}})
    assert err and "Cortana" in out


def test_un_test_rouge_bloque_tout(projet):
    src, store, evo = projet
    d = evo.proposer("Casse", "test", {"agent/calcul.py": "def double(x):\n    return x * 3\n"})
    res = evo.appliquer(d)
    assert res["code"] == 1 and "NON appliquée" in res["sortie"]
    assert "x * 2" in (src / "agent" / "calcul.py").read_text()  # intact


def test_appliquer_puis_annuler(projet):
    src, store, evo = projet
    d = evo.proposer("Triple", "test", {
        "agent/calcul.py": "def double(x):\n    return x * 2\n\ndef triple(x):\n    return x * 3\n",
        "tests/test_triple.py": "from agent.calcul import triple\n\ndef test_triple():\n    assert triple(2) == 6\n"})
    res = evo.appliquer(d)
    assert res["code"] == 0 and res["redemarrer"] and "2 passed" in res["sortie"]
    assert "triple" in (src / "agent" / "calcul.py").read_text() and (src / "tests" / "test_triple.py").exists()
    log = subprocess.run(["git", "-C", str(src), "log", "--oneline"], capture_output=True, text=True).stdout
    assert "jarvis-evolution: Triple" in log
    res = evo.annuler(d)
    assert res["code"] == 0
    assert "triple" not in (src / "agent" / "calcul.py").read_text() and not (src / "tests" / "test_triple.py").exists()
