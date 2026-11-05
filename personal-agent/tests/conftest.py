import os

import pytest

os.environ.setdefault("AGENT_TOKEN", "t" * 32)
os.environ["JARVIS_SANS_PLANIFICATEUR"] = "1"


@pytest.fixture(autouse=True)
def _propre(monkeypatch):
    from agent import etat, net
    net.vider_cache()
    etat.reinitialiser()
    monkeypatch.setattr(net, "_dormir", lambda s: None)  # réessais instantanés en test
    yield
