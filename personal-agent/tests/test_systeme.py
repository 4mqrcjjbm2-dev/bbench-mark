from agent.systeme import conseil_modele, etat, noter_perf


def test_conseil_selon_la_machine():
    assert conseil_modele(8, None) == "qwen3:4b"
    assert conseil_modele(16, None) == "qwen3:8b"
    assert conseil_modele(32, None) == "qwen3:14b"
    assert conseil_modele(16, {"nom": "RTX 3090", "memoire_go": 24}) == "qwen3:32b"
    assert conseil_modele(4, None) == "qwen3:1.7b"


def test_etat_et_remarques(tmp_path, monkeypatch):
    from agent.config import load_settings
    monkeypatch.setenv("AGENT_FOURNISSEUR", "ollama")
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:9")  # rien n'écoute ici
    noter_perf("qwen3:8b", 10.0, 20)
    e = etat(load_settings())
    assert e["memoire_go"] and e["disque_total_go"] > 0 and e["perf"]["tokens_par_seconde"] == 2.0
    assert any("Ollama ne répond pas" in r for r in e["remarques"])
    assert any("lent" in r for r in e["remarques"])
