"""Chaque agent branché, testé hors-ligne avec des réponses au format réel des services."""

from __future__ import annotations

import json
import math

import httpx
import pytest

from agent import agents_outils as ao
from agent.cles import Cles
from agent.storage import JsonStore
from agent.tools import ToolContext, run_tool


def ctx_avec(tmp_path, routes, **kw):
    """routes : liste de (fragment d'URL, réponse ou fonction(request) -> réponse)."""
    appels = []

    def handler(req: httpx.Request) -> httpx.Response:
        appels.append(req)
        for frag, rep in routes:
            if frag in str(req.url):
                return rep(req) if callable(rep) else rep
        return httpx.Response(404)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    c = ToolContext(JsonStore(tmp_path), "Europe/Paris", http=http, cles=Cles(tmp_path), **kw)
    return c, appels


def test_reessai_apres_429_puis_cache(tmp_path):
    n = {"i": 0}

    def flaky(req):
        n["i"] += 1
        return httpx.Response(429) if n["i"] == 1 else httpx.Response(200, json={"bitcoin": {"eur": 60000}})

    c, appels = ctx_avec(tmp_path, [("simple/price", flaky)])
    out, err = run_tool(c, "prix_crypto", {"ids": ["bitcoin"]})
    assert not err and "60000" in out and len(appels) == 2
    run_tool(c, "prix_crypto", {"ids": ["bitcoin"]})
    assert len(appels) == 2  # servi par le cache


def test_prix_secours_coinbase(tmp_path):
    c, _ = ctx_avec(tmp_path, [("simple/price", httpx.Response(503)),
                               ("coinbase.com/v2/prices/BTC-EUR/spot",
                                httpx.Response(200, json={"data": {"amount": "61234.5", "base": "BTC", "currency": "EUR"}}))])
    out, err = run_tool(c, "prix_crypto", {"ids": ["bitcoin"]})
    assert not err and "61234.5" in out and "secours" in out


def test_tendances_crypto(tmp_path):
    trending = {"coins": [{"item": {"name": "Pepe", "symbol": "PEPE", "market_cap_rank": 30,
                                    "data": {"price_change_percentage_24h": {"usd": 12.34}}}}]}
    markets = [{"name": n, "symbol": n.lower(), "current_price": 1, "price_change_percentage_24h": v}
               for n, v in [("A", 5), ("B", -8), ("C", 20), ("D", None)]]
    c, _ = ctx_avec(tmp_path, [("search/trending", httpx.Response(200, json=trending)),
                               ("coins/markets", httpx.Response(200, json=markets))])
    d = json.loads(run_tool(c, "tendances_crypto", {})[0])
    assert d["les_plus_recherchees"][0]["variation_24h_pct"] == 12.3
    assert d["plus_fortes_hausses_top100"][0]["nom"] == "C" and d["plus_fortes_baisses_top100"][0]["nom"] == "B"


STOOQ_OK = "Symbol,Date,Time,Open,High,Low,Close,Volume\nXAUUSD,2026-11-04,22:59:58,2600,2660,2590,2652,0\n"
STOOQ_ND = "Symbol,Date,Time,Open,High,Low,Close,Volume\nNG.F,N/D,N/D,N/D,N/D,N/D,N/D,N/D\n"


def test_vault_et_ledger_partiels(tmp_path):
    def stooq(req):
        return httpx.Response(200, text=STOOQ_ND if req.url.params["s"] == "ng.f" else STOOQ_OK)

    c, _ = ctx_avec(tmp_path, [("stooq.com", stooq),
                               ("frankfurter", httpx.Response(200, json={"date": "2026-11-04", "rates": {"CAD": 1.38, "EUR": 0.92}}))])
    m = json.loads(run_tool(c, "matieres_premieres", {})[0])["matieres"]
    assert m["Or (USD/once)"]["dernier"] == 2652 and m["Or (USD/once)"]["variation_depuis_ouverture_pct"] == 2.0
    assert m["Gaz naturel (USD/MMBtu)"] == "indisponible"  # une source vide n'empêche pas les autres
    f = json.loads(run_tool(c, "marches_financiers", {})[0])
    assert f["devises"]["USD→CAD"] == 1.38 and "S&P 500" in f["indices"]


def test_sniper_lecture_technique(tmp_path):
    prix = [[1_700_000_000_000 + i * 86_400_000, 100 * 1.01 ** i + 3 * math.sin(i)] for i in range(120)]
    c, _ = ctx_avec(tmp_path, [("coins/bitcoin/market_chart", httpx.Response(200, json={"prices": prix}))])
    d = json.loads(run_tool(c, "analyse_technique", {"actif": "bitcoin"})[0])
    assert d["lecture"] == "haussière" and d["score"].endswith("/5") and "pas une prévision" in d["avertissement"]
    out, err = run_tool(c, "analyse_technique", {"actif": "inexistant"})
    assert err and "inconnu" in out.lower()


def test_orca_bitcoin_sans_cle_et_ethereum_avec_cle(tmp_path):
    adr = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
    addr = {"chain_stats": {"funded_txo_sum": 300_000_000, "spent_txo_sum": 100_000_000, "tx_count": 4},
            "mempool_stats": {"tx_count": 0}}
    txs = [{"txid": "a" * 64, "status": {"confirmed": True, "block_time": 1793800000},
            "vin": [], "vout": [{"scriptpubkey_address": adr, "value": 50_000_000}]}]
    c, _ = ctx_avec(tmp_path, [(f"address/{adr}/txs", httpx.Response(200, json=txs)),
                               (f"address/{adr}", httpx.Response(200, json=addr))])
    d = json.loads(run_tool(c, "portefeuille_public", {"adresse": adr})[0])
    assert d["solde_btc"] == 2.0 and d["dernieres"][0]["net_btc"] == 0.5

    eth = "0x" + "a" * 40
    out, err = run_tool(c, "portefeuille_public", {"adresse": eth})
    assert err and "Clés API" in out  # dit exactement où coller la clé
    c.cles.definir("ETHERSCAN_API_KEY", "A" * 34)
    c2, appels = ctx_avec(tmp_path, [
        ("action=balance", httpx.Response(200, json={"status": "1", "message": "OK", "result": str(3 * 10**18)})),
        ("action=txlist", httpx.Response(200, json={"status": "1", "result": [
            {"hash": "0x" + "b" * 64, "to": eth, "value": str(10**18), "timeStamp": "1793800000"}]}))])
    d = json.loads(run_tool(c2, "portefeuille_public", {"adresse": eth})[0])
    assert d["solde_eth"] == 3.0 and d["dernieres"][0]["sens"] == "entrée"
    assert "apikey=" + "A" * 34 in str(appels[0].url)
    out, err = run_tool(c2, "portefeuille_public", {"adresse": "ma phrase secrète"})
    assert err and "clé privée" in out


def test_beacon_notification_et_rapport_partiel(tmp_path):
    envoyes = []

    def ntfy(req):
        envoyes.append(json.loads(req.content))
        return httpx.Response(200, json={"id": "x"})

    c, _ = ctx_avec(tmp_path, [
        ("ntfy.sh", ntfy),
        ("simple/price", httpx.Response(200, json={"bitcoin": {"eur": 61200, "eur_24h_change": 2.3}})),
        ("search/trending", httpx.Response(500)),
        ("stooq.com", httpx.Response(200, text=STOOQ_OK))])
    c.cles.generer_auto()
    topic = c.cles.get("NTFY_TOPIC")
    assert topic.startswith("jarvis-") and len(topic) >= 20
    assert run_tool(c, "notifier", {"titre": "Test", "message": "Bonjour", "priorite": "haute"})[0].startswith("Notification")
    assert envoyes[0]["topic"] == topic and envoyes[0]["priority"] == 4
    texte, err = run_tool(c, "rapport_du_jour", {"envoyer": True})
    assert not err and "BTC 61 200 €" in texte and "Tâches en cours : 0" in texte and "Envoyé" in texte
    assert "Rapport Jarvis" == envoyes[1]["title"]  # rapport envoyé malgré les tendances en panne


def test_caro_ne_notifie_pas(tmp_path):
    c, appels = ctx_avec(tmp_path, [], lecture_seule=True)
    c.cles.generer_auto()
    out, err = run_tool(c, "notifier", {"titre": "x", "message": "y"})
    assert err and "Cortana" in out and not appels


def test_coffre_a_cles(tmp_path):
    k = Cles(tmp_path)
    with pytest.raises(ValueError):
        k.definir("ETHERSCAN_API_KEY", "trop court")
    k.definir("ETHERSCAN_API_KEY", "ABCDEFGHIJKLMNOPQRSTUVWXYZ123456")
    st = {s["nom"]: s for s in k.statut()}
    assert st["ETHERSCAN_API_KEY"]["apercu"] == "•••• 3456"  # jamais la clé en clair
    assert oct((tmp_path / "cles.json").stat().st_mode)[-3:] == "600"


def test_specialiste_et_attribution(tmp_path, monkeypatch):
    from anthropic.types.beta import BetaMessage

    from agent.config import load_settings
    from agent.core import Agent, agent_de

    def msg(content, stop):
        return BetaMessage.model_validate({"id": "m", "type": "message", "role": "assistant", "model": "x",
                                          "content": content, "stop_reason": stop, "stop_sequence": None,
                                          "usage": {"input_tokens": 1, "output_tokens": 1}})

    class Fake:
        def __init__(self):
            self.calls, self.replies = [], [
                msg([{"type": "tool_use", "id": "s1", "name": "consulter_specialiste",
                      "input": {"agent": "festa", "demande": "Quoi vendre pour Noël ?"}}], "tool_use"),
                msg([{"type": "text", "text": "Lumières LED et pulls de Noël, selon FESTA."}], "end_turn"),  # sous-agent
                msg([{"type": "text", "text": "FESTA conseille les lumières LED."}], "end_turn")]
            self.beta = type("B", (), {"messages": self})()

        def create(self, **kw):
            self.calls.append(kw)
            return self.replies.pop(0)

    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    fake = Fake()
    rep = Agent(load_settings(), client=fake).ask("Quoi vendre pour Noël ?")
    assert rep.text == "FESTA conseille les lumières LED."
    assert rep.events[0]["agent"] == "festa" and not rep.events[0]["erreur"]
    assert "Tu es FESTA" in fake.calls[1]["system"]
    assert agent_de("prix_crypto", {}, "caro") == "pulse" and agent_de("inconnu", {}, "caro") == "caro"
