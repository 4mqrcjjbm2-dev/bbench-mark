import os

import pytest

os.environ.setdefault("AGENT_TOKEN", "t" * 32)
os.environ["JARVIS_SANS_PLANIFICATEUR"] = "1"
os.environ.setdefault("AGENT_FOURNISSEUR", "anthropic")
os.environ.setdefault("AGENT_HORS_LIGNE", "0")
os.environ["JARVIS_REDEMARRAGE_AUTO"] = "0"  # jamais de vrai redémarrage pendant les tests  # pas de vraie vérification réseau dans les tests  # les tests historiques visent Claude ; Ollama a les siens


@pytest.fixture(autouse=True)
def _propre(monkeypatch, tmp_path_factory):
    monkeypatch.setenv("AGENT_ATELIER", str(tmp_path_factory.mktemp("atelier")))
    from agent import etat, net
    net.vider_cache()
    etat.reinitialiser()
    monkeypatch.setattr(net, "_dormir", lambda s: None)  # réessais instantanés en test
    yield
