"""Les outils des agents du Catalogue, chacun sur son chemin le plus fiable.

Principes :
- source gratuite SANS clé d'abord ; une source de secours quand c'est possible ;
- réessais et cache courts (net.py) pour que ça marche du premier coup ;
- un rapport qui s'assemble même si une partie des sources ne répond pas ;
- lecture seule partout : aucun ordre, aucune signature, aucune copie de trade.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any, Callable

from . import net
from .backtest import BacktestErreur, _rsi, recuperer_prix

COINGECKO = "https://api.coingecko.com/api/v3"
COINBASE = "https://api.coinbase.com/v2/prices"
STOOQ = "https://stooq.com/q/l/"
FRANKFURTER = "https://api.frankfurter.app/latest"
MEMPOOL = "https://mempool.space/api"
ETHERSCAN = "https://api.etherscan.io/v2/api"
NTFY = "https://ntfy.sh/"

SYMBOLES_COINBASE = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "dogecoin": "DOGE", "cardano": "ADA",
                     "ripple": "XRP", "litecoin": "LTC", "polkadot": "DOT", "avalanche-2": "AVAX",
                     "chainlink": "LINK", "polygon-ecosystem-token": "POL", "bitcoin-cash": "BCH"}


class OutilErreur(Exception):
    pass


def _r(x: float | None, n: int = 2) -> float | None:
    return None if x is None else round(x, n)


# --- PULSE : prix (avec secours) et tendances crypto ------------------------------------

def prix_secours_coinbase(http, ids: list[str], devise: str) -> dict:
    """Si CoinGecko tombe : prix au comptant Coinbase (sans variation 24 h)."""
    out = {}
    for i in ids:
        sym = SYMBOLES_COINBASE.get(i)
        if not sym:
            continue
        try:
            d = net.get_json(http, f"{COINBASE}/{sym}-{devise.upper()}/spot", service="coinbase", ttl=30)
            out[i] = {devise: float(d["data"]["amount"]), "source": "coinbase (secours)"}
        except (net.ServiceErreur, KeyError, ValueError):
            continue
    return out


def tendances_crypto(ctx, args: dict) -> str:
    devise = (args.get("devise") or "eur").lower()
    res: dict[str, Any] = {}
    try:
        t = net.get_json(ctx.http, f"{COINGECKO}/search/trending", service="coingecko", ttl=300)
        res["les_plus_recherchees"] = [
            {"nom": c["item"]["name"], "symbole": c["item"]["symbol"], "rang": c["item"].get("market_cap_rank"),
             "variation_24h_pct": _r((c["item"].get("data") or {}).get("price_change_percentage_24h", {}).get("usd"), 1)}
            for c in t.get("coins", [])[:7]]
    except net.ServiceErreur as e:
        res["les_plus_recherchees"] = str(e)
    try:
        m = net.get_json(ctx.http, f"{COINGECKO}/coins/markets", service="coingecko", ttl=120,
                         params={"vs_currency": devise, "order": "market_cap_desc", "per_page": 100, "page": 1,
                                 "price_change_percentage": "24h"})
        m = [c for c in m if c.get("price_change_percentage_24h") is not None]
        m.sort(key=lambda c: c["price_change_percentage_24h"], reverse=True)
        f = lambda c: {"nom": c["name"], "symbole": c["symbol"].upper(), "prix": c["current_price"],  # noqa: E731
                       "variation_24h_pct": _r(c["price_change_percentage_24h"], 1)}
        res["plus_fortes_hausses_top100"] = [f(c) for c in m[:5]]
        res["plus_fortes_baisses_top100"] = [f(c) for c in m[-5:][::-1]]
    except net.ServiceErreur as e:
        res["mouvements_top100"] = str(e)
    return json.dumps(res, ensure_ascii=False)


# --- LEDGER et VAULT : marchés, devises, matières premières (Stooq + Frankfurter) ----------

def _stooq(http, symbole: str) -> dict | None:
    texte = net.get_text(http, STOOQ, service="stooq", ttl=300,
                         params={"s": symbole, "f": "sd2t2ohlcv", "h": "", "e": "csv"})
    lignes = list(csv.DictReader(io.StringIO(texte)))
    if not lignes or lignes[0].get("Close") in (None, "", "N/D"):
        return None
    l = lignes[0]
    o, c = float(l["Open"]), float(l["Close"])
    return {"dernier": c, "date": l.get("Date"), "variation_depuis_ouverture_pct": _r((c / o - 1) * 100 if o else None)}


INDICES = {"S&P 500": "^spx", "Nasdaq": "^ndq", "Dow Jones": "^dji"}
MATIERES = {"Or (USD/once)": "xauusd", "Argent (USD/once)": "xagusd",
            "Pétrole WTI (USD/baril)": "cl.f", "Gaz naturel (USD/MMBtu)": "ng.f"}


def _serie_stooq(ctx, table: dict) -> dict:
    out = {}
    for nom, sym in table.items():
        try:
            out[nom] = _stooq(ctx.http, sym) or "indisponible"
        except (net.ServiceErreur, ValueError, KeyError):
            out[nom] = "indisponible"
    return out


def marches_financiers(ctx, args: dict) -> str:
    res: dict[str, Any] = {"indices": _serie_stooq(ctx, INDICES)}
    try:
        d = net.get_json(ctx.http, FRANKFURTER, service="frankfurter", ttl=1800, params={"from": "USD", "to": "CAD,EUR"})
        res["devises"] = {"USD→CAD": d["rates"].get("CAD"), "USD→EUR": d["rates"].get("EUR"), "date": d.get("date")}
    except (net.ServiceErreur, KeyError):
        res["devises"] = "indisponible"
    res["note"] = "Variation des indices calculée depuis l'ouverture du jour (Stooq)."
    return json.dumps(res, ensure_ascii=False)


def matieres_premieres(ctx, args: dict) -> str:
    return json.dumps({"matieres": _serie_stooq(ctx, MATIERES),
                       "note": "Prix de marché Stooq ; contrats à terme pour le pétrole et le gaz."}, ensure_ascii=False)


# --- Sniper Pro : lecture technique (description, jamais un ordre) ------------------------

def _ema(v: list[float], n: int) -> list[float]:
    k, out = 2 / (n + 1), [v[0]]
    for x in v[1:]:
        out.append(x * k + out[-1] * (1 - k))
    return out


def analyse_technique(ctx, args: dict) -> str:
    actif = str(args.get("actif") or "").strip().lower()
    if not actif:
        raise OutilErreur("Paramètre 'actif' manquant (identifiant CoinGecko, ex: bitcoin).")
    devise = (args.get("devise") or "eur").lower()
    try:
        closes = [c for _, c in recuperer_prix(ctx.http, actif, devise, 120)]
    except BacktestErreur as e:
        raise OutilErreur(str(e)) from e
    if len(closes) < 60:
        raise OutilErreur("Pas assez d'historique pour une lecture fiable.")
    c = closes[-1]
    mm20, mm50 = sum(closes[-20:]) / 20, sum(closes[-50:]) / 50
    rsi = _rsi(closes, 14)[-1]
    macd = [a - b for a, b in zip(_ema(closes, 12), _ema(closes, 26))]
    signal = _ema(macd, 9)
    ecart = (sum((x - mm20) ** 2 for x in closes[-20:]) / 20) ** 0.5
    haut, bas = mm20 + 2 * ecart, mm20 - 2 * ecart
    conditions = {
        "prix au-dessus de la MM50 (tendance de fond)": c > mm50,
        "MM20 au-dessus de la MM50": mm20 > mm50,
        "RSI entre 45 et 70 (élan sans excès)": rsi is not None and 45 <= rsi <= 70,
        "MACD au-dessus de son signal": macd[-1] > signal[-1],
        "prix à l'intérieur des bandes de Bollinger": bas <= c <= haut,
    }
    score = sum(conditions.values())
    lecture = "haussière" if score >= 4 else "baissière" if score <= 1 else "mitigée"
    return json.dumps({
        "actif": actif, "devise": devise, "dernier_prix": _r(c, 4), "mm20": _r(mm20, 4), "mm50": _r(mm50, 4),
        "rsi14": _r(rsi, 1), "macd": _r(macd[-1], 4), "signal_macd": _r(signal[-1], 4),
        "bollinger": {"haut": _r(haut, 4), "bas": _r(bas, 4)},
        "conditions": conditions, "score": f"{score}/5", "lecture": lecture,
        "avertissement": "Lecture du passé (bougies quotidiennes), pas une prévision ni un conseil. "
                         "À valider par un backtest avant toute idée de trade.",
    }, ensure_ascii=False)


# --- ORCA : portefeuilles publics (lecture seule) ----------------------------------------

RE_BTC = re.compile(r"^(bc1[a-z0-9]{25,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")
RE_ETH = re.compile(r"^0x[a-fA-F0-9]{40}$")


def portefeuille_public(ctx, args: dict) -> str:
    adresse = str(args.get("adresse") or "").strip()
    if RE_BTC.match(adresse):
        d = net.get_json(ctx.http, f"{MEMPOOL}/address/{adresse}", service="mempool", ttl=60)
        cs, ms = d["chain_stats"], d.get("mempool_stats", {})
        solde = (cs["funded_txo_sum"] - cs["spent_txo_sum"]) / 1e8
        txs = net.get_json(ctx.http, f"{MEMPOOL}/address/{adresse}/txs", service="mempool", ttl=60)[:5]
        dernieres = []
        for tx in txs:
            recu = sum(o.get("value", 0) for o in tx.get("vout", []) if o.get("scriptpubkey_address") == adresse)
            envoye = sum((i.get("prevout") or {}).get("value", 0) for i in tx.get("vin", [])
                         if (i.get("prevout") or {}).get("scriptpubkey_address") == adresse)
            dernieres.append({"txid": tx["txid"][:12] + "…", "net_btc": _r((recu - envoye) / 1e8, 8),
                              "confirmee": (tx.get("status") or {}).get("confirmed", False),
                              "horodatage": (tx.get("status") or {}).get("block_time")})
        return json.dumps({"reseau": "bitcoin", "adresse": adresse, "solde_btc": _r(solde, 8),
                           "nb_transactions": cs.get("tx_count"), "en_attente": ms.get("tx_count", 0),
                           "dernieres": dernieres, "note": "Données publiques. Alertes seulement, aucune copie de trade."},
                          ensure_ascii=False)
    if RE_ETH.match(adresse):
        cle = ctx.cles.get("ETHERSCAN_API_KEY") if ctx.cles else ""
        if not cle:
            raise OutilErreur("ORCA a besoin d'une clé Etherscan gratuite pour Ethereum : colle-la dans "
                              "Connexions → Clés API (etherscan.io/myapikey). Les adresses Bitcoin marchent sans clé.")
        base = {"chainid": 1, "module": "account", "address": adresse, "apikey": cle}
        b = net.get_json(ctx.http, ETHERSCAN, service="etherscan", ttl=60, params={**base, "action": "balance", "tag": "latest"})
        if b.get("status") != "1":
            raise OutilErreur(f"Etherscan : {b.get('result') or b.get('message')}")
        t = net.get_json(ctx.http, ETHERSCAN, service="etherscan", ttl=60,
                         params={**base, "action": "txlist", "page": 1, "offset": 5, "sort": "desc"})
        dernieres = [{"hash": x["hash"][:12] + "…", "sens": "entrée" if x["to"].lower() == adresse.lower() else "sortie",
                      "eth": _r(int(x["value"]) / 1e18, 6), "horodatage": int(x["timeStamp"])}
                     for x in (t.get("result") or [])[:5] if isinstance(x, dict)]
        return json.dumps({"reseau": "ethereum", "adresse": adresse, "solde_eth": _r(int(b["result"]) / 1e18, 6),
                           "dernieres": dernieres, "note": "Données publiques. Alertes seulement, aucune copie de trade."},
                          ensure_ascii=False)
    raise OutilErreur("Adresse non reconnue. Donne une adresse Bitcoin (bc1…, 1…, 3…) ou Ethereum (0x…). "
                      "Ne donne jamais une clé privée ni une phrase de récupération.")


# --- BEACON : notifications iPhone (ntfy) et rapport du jour --------------------------------

def envoyer_notification(http, topic: str, titre: str, message: str, priorite: int = 3,
                         lien: str | None = None) -> None:
    corps = {"topic": topic, "title": titre[:120], "message": message[:3500], "priority": priorite, "tags": ["robot"]}
    if lien:
        corps["click"] = lien
    net.requete(http, "POST", NTFY, service="ntfy", json=corps, essais=3)


def notifier(ctx, args: dict) -> str:
    if ctx.lecture_seule:
        raise OutilErreur("Caro n'envoie pas de notification : demande à Cortana.")
    topic = ctx.cles.get("NTFY_TOPIC") if ctx.cles else ""
    if not topic:
        raise OutilErreur("Le sujet de notifications n'est pas encore créé : ouvre la page Jarvis une fois.")
    prio = {"basse": 2, "normale": 3, "haute": 4, "urgente": 5}.get(args.get("priorite") or "normale", 3)
    envoyer_notification(ctx.http, topic, str(args.get("titre") or "Jarvis"), str(args.get("message") or ""),
                         prio, args.get("lien"))
    return "Notification envoyée sur l'iPhone."


def rapport_texte(ctx) -> str:
    """Le rapport du matin, assemblé sans appel à l'IA : rapide, gratuit, et partiel plutôt qu'absent."""
    parties = []
    try:
        p = net.get_json(ctx.http, f"{COINGECKO}/simple/price", service="coingecko", ttl=60,
                         params={"ids": "bitcoin,ethereum,solana", "vs_currencies": "eur", "include_24hr_change": "true"})
        parties.append("Crypto : " + ", ".join(
            f"{n} {p[i]['eur']:,.0f} € ({p[i].get('eur_24h_change', 0):+.1f} %)".replace(",", " ")
            for i, n in (("bitcoin", "BTC"), ("ethereum", "ETH"), ("solana", "SOL")) if i in p))
    except net.ServiceErreur:
        parties.append("Crypto : indisponible.")
    try:
        t = net.get_json(ctx.http, f"{COINGECKO}/search/trending", service="coingecko", ttl=300)
        noms = [c["item"]["symbol"] for c in t.get("coins", [])[:3]]
        if noms:
            parties.append("Tendances : " + ", ".join(noms) + ".")
    except net.ServiceErreur:
        pass
    ind = _serie_stooq(ctx, {"S&P 500": "^spx"}).get("S&P 500")
    if isinstance(ind, dict) and ind.get("variation_depuis_ouverture_pct") is not None:
        parties.append(f"S&P 500 : {ind['dernier']:,.0f} ({ind['variation_depuis_ouverture_pct']:+.1f} %)".replace(",", " "))
    mat = _serie_stooq(ctx, {"Or": "xauusd", "Pétrole": "cl.f"})
    m = [f"{k} {v['dernier']:,.0f} $".replace(",", " ") for k, v in mat.items() if isinstance(v, dict)]
    if m:
        parties.append("Matières : " + ", ".join(m) + ".")
    taches = [t["titre"] for t in ctx.store.list_items("taches") if not t.get("faite")]
    parties.append(f"Tâches en cours : {len(taches)}" + (" — " + " ; ".join(taches[:3]) if taches else "") + ".")
    parties.append("Données publiques, pas un conseil financier.")
    return "\n".join(parties)


def rapport_du_jour(ctx, args: dict) -> str:
    texte = rapport_texte(ctx)
    if args.get("envoyer"):
        if ctx.lecture_seule:
            return texte + "\n(Caro n'envoie pas de notification : demande à Cortana.)"
        topic = ctx.cles.get("NTFY_TOPIC") if ctx.cles else ""
        if topic:
            envoyer_notification(ctx.http, topic, "Rapport Jarvis", texte)
            texte += "\n(Envoyé sur l'iPhone.)"
    return texte


# --- Spécialistes : un sous-agent Claude avec son propre métier et la recherche web ---------

SPECIALISTES = {
    "echo": ("ECHO", "radar des tendances sur les réseaux sociaux (TikTok, Instagram, YouTube Shorts). Donne les "
             "sujets, produits et hashtags qui montent en ce moment, avec la date des sources."),
    "silk": ("SILK", "chasseur de tendances mode. Repère les styles de vêtements qui commencent à se vendre, "
             "les marques et les prix, et ce qu'un petit commerçant pourrait stocker."),
    "aura": ("AURA", "chasseuse de tendances beauté. Cosmétiques et parfums qui montent, avec les produits précis."),
    "festa": ("FESTA", "calendrier des fêtes et des saisons. Prévois ce qui va se vendre pour les prochaines fêtes "
              "(Halloween, Noël, Saint-Valentin, etc.) et quand commencer à préparer, avec des dates."),
    "forge": ("FORGE", "coach des nouvelles compagnies, au Québec et au Canada. Étapes concrètes pour lancer et faire "
              "grandir une petite entreprise : enregistrement, taxes, produits faciles à vendre, premiers clients."),
    "neon": ("NEON", "designer d'espace cyber-tech. Idées de déco pour chambre ou bureau (LED, affiches numériques, "
             "accessoires de setup), avec budget approximatif."),
    "rig": ("RIG", "technicien gaming. Optimise un PC de jeu (performance, stockage, pilotes, réglages Windows) et "
            "propose des setups selon un budget. Étapes simples et sûres."),
    "aegis": ("AEGIS", "garde du corps numérique. Fais un checkup guidé de l'appareil ou du compte dont on parle, "
              "explique les risques en mots simples et donne les étapes pour se protéger. Ne demande jamais de mot "
              "de passe ni de clé."),
    "prism": ("PRISM", "analyste. Décompose une information compliquée (marché, nouvelle, document) en points clairs : "
              "ce qui se passe, pourquoi ça compte, ce qu'on ne sait pas encore."),
    "pub": ("Agent Pub", "publicitaire. Rédige des annonces prêtes à publier (texte court, accroche, hashtags) adaptées "
            "à chaque réseau. Tu rédiges seulement : la publication reste au propriétaire."),
}


def consulter_specialiste(ctx, args: dict) -> str:
    agent = str(args.get("agent") or "").lower()
    if agent not in SPECIALISTES:
        raise OutilErreur(f"Spécialiste inconnu. Choix : {', '.join(SPECIALISTES)}.")
    demande = str(args.get("demande") or "").strip()
    if not demande:
        raise OutilErreur("Paramètre 'demande' manquant.")
    if not ctx.specialiste:
        raise OutilErreur("Les spécialistes ne sont pas disponibles dans ce contexte.")
    return ctx.specialiste(agent, demande)


# --- Déclarations ------------------------------------------------------------------------

def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


OUTILS_AGENTS: list[tuple[dict, Callable]] = [
    ({"name": "tendances_crypto",
      "description": "PULSE : cryptos les plus recherchées et plus fortes hausses/baisses du top 100 sur 24 h.",
      "input_schema": _obj({"devise": {"type": "string"}}, [])}, tendances_crypto),
    ({"name": "marches_financiers",
      "description": "LEDGER : S&P 500, Nasdaq, Dow Jones (variation du jour) et taux USD→CAD, USD→EUR.",
      "input_schema": _obj({}, [])}, marches_financiers),
    ({"name": "matieres_premieres",
      "description": "VAULT : prix de l'or, de l'argent, du pétrole WTI et du gaz naturel.",
      "input_schema": _obj({}, [])}, matieres_premieres),
    ({"name": "analyse_technique",
      "description": ("Sniper Pro : lecture technique d'une crypto sur bougies quotidiennes (MM20/50, RSI 14, MACD, "
                      "Bollinger, score sur 5 conditions). Description du passé, jamais un conseil."),
      "input_schema": _obj({"actif": {"type": "string", "description": "Identifiant CoinGecko"},
                            "devise": {"type": "string"}}, ["actif"])}, analyse_technique),
    ({"name": "portefeuille_public",
      "description": ("ORCA : solde et dernières transactions d'une adresse PUBLIQUE Bitcoin (sans clé) ou Ethereum "
                      "(clé Etherscan). Lecture seule."),
      "input_schema": _obj({"adresse": {"type": "string"}}, ["adresse"])}, portefeuille_public),
    ({"name": "notifier",
      "description": "BEACON : envoie une notification sur l'iPhone (app ntfy). Seulement si on te le demande.",
      "input_schema": _obj({"titre": {"type": "string"}, "message": {"type": "string"},
                            "priorite": {"type": "string", "enum": ["basse", "normale", "haute", "urgente"]},
                            "lien": {"type": "string"}}, ["titre", "message"])}, notifier),
    ({"name": "rapport_du_jour",
      "description": ("BEACON : rapport du moment (crypto, tendances, S&P 500, or, pétrole, tâches). "
                      "envoyer=true l'envoie aussi en notification sur l'iPhone."),
      "input_schema": _obj({"envoyer": {"type": "boolean"}}, [])}, rapport_du_jour),
    ({"name": "consulter_specialiste",
      "description": ("Confie une question à un agent spécialiste du Catalogue, qui fait sa propre recherche web : "
                      + "; ".join(f"{k} = {v[0]}, {v[1].split('.')[0]}" for k, v in SPECIALISTES.items())),
      "input_schema": _obj({"agent": {"type": "string", "enum": list(SPECIALISTES)},
                            "demande": {"type": "string"}}, ["agent", "demande"])}, consulter_specialiste),
]
