"""Backtests honnêtes sur l'historique des prix (aucun ordre réel, jamais).

Règles (compétence `backtest` du Cerveau) :
- aucune vision du futur : le signal est calculé à la clôture du jour J avec les données
  connues ce jour-là, et exécuté à la clôture du jour J+1 ;
- frais comptés à chaque achat et à chaque vente ;
- on rapporte toujours la pire chute et le taux de réussite, pas seulement le gain.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

COINGECKO = "https://api.coingecko.com/api/v3"

STRATEGIES = {
    "tendance": {
        "nom": "Tendance (MM20/MM50)",
        "regle": "Entrer si clôture > MM20 et MM20 > MM50 ; sortir si clôture < MM20 ou stop.",
        "params": {"rapide": 20, "lente": 50},
    },
    "croisement_mm": {
        "nom": "Croisement de moyennes",
        "regle": "Entrer quand MM rapide passe au-dessus de MM lente ; sortir au croisement inverse ou stop.",
        "params": {"rapide": 9, "lente": 21},
    },
    "rsi": {
        "nom": "Retour à la moyenne (RSI)",
        "regle": "Entrer si RSI(14) < seuil bas ; sortir si RSI > seuil haut ou stop.",
        "params": {"periode": 14, "bas": 30, "haut": 55},
    },
}


class BacktestErreur(Exception):
    pass


def recuperer_prix(http: httpx.Client, actif: str, devise: str, jours: int) -> list[tuple[float, float]]:
    r = http.get(f"{COINGECKO}/coins/{actif}/market_chart",
                 params={"vs_currency": devise, "days": jours, "interval": "daily"})
    if r.status_code == 404:
        raise BacktestErreur(f"Actif inconnu sur CoinGecko : {actif}")
    r.raise_for_status()
    prix = [(ts / 1000, p) for ts, p in r.json().get("prices", []) if p]
    # CoinGecko ajoute parfois le point « maintenant » en plus du dernier jour : on garde un point par jour.
    par_jour: dict[str, tuple[float, float]] = {}
    for ts, p in prix:
        par_jour[time.strftime("%Y-%m-%d", time.gmtime(ts))] = (ts, p)
    return [par_jour[k] for k in sorted(par_jour)]


def _mm(valeurs: list[float], n: int, i: int) -> float | None:
    if i + 1 < n:
        return None
    return sum(valeurs[i + 1 - n:i + 1]) / n


def _rsi(valeurs: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(valeurs)
    if len(valeurs) <= n:
        return out
    gains = [max(valeurs[i] - valeurs[i - 1], 0) for i in range(1, len(valeurs))]
    pertes = [max(valeurs[i - 1] - valeurs[i], 0) for i in range(1, len(valeurs))]
    g, p = sum(gains[:n]) / n, sum(pertes[:n]) / n
    for i in range(n, len(valeurs)):
        if i > n:  # lissage de Wilder
            g = (g * (n - 1) + gains[i - 1]) / n
            p = (p * (n - 1) + pertes[i - 1]) / n
        out[i] = 100.0 if p == 0 else 100 - 100 / (1 + g / p)
    return out


@dataclass
class Parametres:
    strategie: str = "tendance"
    stop_pct: float = 5.0
    frais_pct: float = 0.2
    rapide: int | None = None
    lente: int | None = None
    bas: float | None = None
    haut: float | None = None


def _signaux(closes: list[float], p: Parametres) -> list[str | None]:
    """'entrer' / 'sortir' / None pour chaque jour, avec les seules données connues ce jour-là."""
    defaut = STRATEGIES[p.strategie]["params"]
    sig: list[str | None] = [None] * len(closes)
    if p.strategie in ("tendance", "croisement_mm"):
        rapide, lente = p.rapide or defaut["rapide"], p.lente or defaut["lente"]
        if rapide >= lente:
            raise BacktestErreur("La moyenne rapide doit être plus courte que la lente.")
        for i in range(len(closes)):
            mr, ml = _mm(closes, rapide, i), _mm(closes, lente, i)
            if mr is None or ml is None:
                continue
            if p.strategie == "tendance":
                sig[i] = "entrer" if closes[i] > mr and mr > ml else ("sortir" if closes[i] < mr else None)
            else:
                mr0, ml0 = _mm(closes, rapide, i - 1), _mm(closes, lente, i - 1)
                if mr0 is not None and ml0 is not None:
                    if mr0 <= ml0 and mr > ml:
                        sig[i] = "entrer"
                    elif mr0 >= ml0 and mr < ml:
                        sig[i] = "sortir"
    elif p.strategie == "rsi":
        bas, haut = p.bas or defaut["bas"], p.haut or defaut["haut"]
        for i, r in enumerate(_rsi(closes, defaut["periode"])):
            if r is not None:
                sig[i] = "entrer" if r < bas else ("sortir" if r > haut else None)
    else:
        raise BacktestErreur(f"Stratégie inconnue. Choix : {', '.join(STRATEGIES)}")
    return sig


def _pire_chute(courbe: list[float]) -> float:
    sommet, pire = courbe[0], 0.0
    for v in courbe:
        sommet = max(sommet, v)
        pire = min(pire, v / sommet - 1)
    return pire * 100


def _echantillon(courbe: list[float], n: int = 80) -> list[float]:
    if len(courbe) <= n:
        return [round(v, 2) for v in courbe]
    pas = (len(courbe) - 1) / (n - 1)
    return [round(courbe[round(i * pas)], 2) for i in range(n)]


def executer(prix: list[tuple[float, float]], p: Parametres) -> dict:
    if len(prix) < 60:
        raise BacktestErreur("Pas assez d'historique (60 jours minimum).")
    closes = [c for _, c in prix]
    sig = _signaux(closes, p)
    frais = p.frais_pct / 100
    capital, quantite, entree = 100.0, 0.0, 0.0
    trades: list[float] = []
    courbe: list[float] = []

    for j in range(len(closes)):
        c = closes[j]
        if quantite:
            # stop-loss vérifié sur la clôture du jour
            if c <= entree * (1 - p.stop_pct / 100):
                capital = quantite * c * (1 - frais)
                trades.append(capital / (quantite * entree / (1 - frais)) - 1)
                quantite = 0.0
            elif j > 0 and sig[j - 1] == "sortir":  # signal d'hier, exécuté aujourd'hui
                capital = quantite * c * (1 - frais)
                trades.append(capital / (quantite * entree / (1 - frais)) - 1)
                quantite = 0.0
        elif j > 0 and sig[j - 1] == "entrer":
            quantite, entree = capital * (1 - frais) / c, c
        courbe.append(quantite * c if quantite else capital)

    if quantite:  # position encore ouverte : valorisée à la dernière clôture (sans la vendre)
        trades.append(quantite * closes[-1] * (1 - frais) / (quantite * entree / (1 - frais)) - 1)

    gagnants = [t for t in trades if t > 0]
    perdants = [t for t in trades if t <= 0]
    bh = [100 * c / closes[0] for c in closes]
    pct = lambda x: round(x * 100, 1)  # noqa: E731
    return {
        "strategie": p.strategie,
        "nom": STRATEGIES[p.strategie]["nom"],
        "regle": STRATEGIES[p.strategie]["regle"],
        "debut": time.strftime("%Y-%m-%d", time.gmtime(prix[0][0])),
        "fin": time.strftime("%Y-%m-%d", time.gmtime(prix[-1][0])),
        "jours": len(closes),
        "stop_pct": p.stop_pct,
        "frais_pct": p.frais_pct,
        "rendement_pct": round(courbe[-1] - 100, 1),
        "buy_hold_pct": round(bh[-1] - 100, 1),
        "pire_chute_pct": round(_pire_chute(courbe), 1),
        "buy_hold_pire_chute_pct": round(_pire_chute(bh), 1),
        "nb_trades": len(trades),
        "taux_reussite_pct": round(100 * len(gagnants) / len(trades), 0) if trades else None,
        "gain_moyen_pct": pct(sum(gagnants) / len(gagnants)) if gagnants else None,
        "perte_moyenne_pct": pct(sum(perdants) / len(perdants)) if perdants else None,
        "position_ouverte": bool(quantite),
        "courbe": _echantillon(courbe),
        "courbe_buy_hold": _echantillon(bh),
        "avertissement": "Résultat passé, sans garantie pour le futur. Simulation uniquement, aucun ordre réel.",
    }
