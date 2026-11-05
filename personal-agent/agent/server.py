"""Serveur HTTP : appelé par le Raccourci iPhone et par le tableau de bord web.

Lancement : uvicorn agent.server:app --host 0.0.0.0 --port 8787
Tableau de bord : ouvre http://<serveur>:8787/ dans Safari.
"""

from __future__ import annotations

import datetime as dt
import hmac
import logging
import os
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import httpx

from . import etat
from .backtest import STRATEGIES
from .config import load_settings
from .core import EFFORTS, Agent
from typing import Literal

from .catalogue import CARO_CATALOGUE, GROUPES, PERSONAS, agents_pour_page
from .agents_outils import envoyer_notification, rapport_texte
from .cles import CLES
from .tools import CAPACITES, ToolContext, ToolError, lancer_backtest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
settings = load_settings()

if len(settings.agent_token) < 24:
    raise RuntimeError(
        "AGENT_TOKEN absent ou trop court (24 caractères minimum). "
        "Génère-en un avec : python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

STATIC = Path(__file__).parent / "static"
log = logging.getLogger("jarvis")


def envoyer_rapport(agent) -> str:
    """BEACON : assemble le rapport et l'envoie sur l'iPhone (ntfy)."""
    ctx = ToolContext(agent.store, settings.timezone, cles=agent.cles)
    try:
        texte = rapport_texte(ctx)
        envoyer_notification(ctx.http, agent.cles.get("NTFY_TOPIC"), "Rapport Jarvis", texte)
        return texte
    finally:
        ctx.http.close()


def _beacon_boucle(arret: threading.Event) -> None:
    """Envoie le rapport du matin une fois par jour, à l'heure choisie (rattrapage jusqu'à 2 h après)."""
    while not arret.wait(30):
        try:
            agent = get_agent()
            o = agent.options()
            if not o["beacon_actif"]:
                continue
            maintenant = dt.datetime.now(ZoneInfo(settings.timezone))
            h, m = map(int, o["beacon_heure"].split(":"))
            prevu = maintenant.replace(hour=h, minute=m, second=0, microsecond=0)
            deja = agent.store.get_options().get("beacon_dernier")
            if prevu <= maintenant < prevu + dt.timedelta(hours=2) and deja != maintenant.date().isoformat():
                agent.store.set_options(beacon_dernier=maintenant.date().isoformat())
                envoyer_rapport(agent)
                log.info("BEACON : rapport du matin envoyé")
        except Exception:  # noqa: BLE001 - la boucle ne doit jamais mourir
            log.exception("BEACON")


@asynccontextmanager
async def lifespan(_app):
    arret = threading.Event()
    if os.environ.get("JARVIS_SANS_PLANIFICATEUR") != "1":
        threading.Thread(target=_beacon_boucle, args=(arret,), daemon=True).start()
    yield
    arret.set()


app = FastAPI(title="Jarvis", docs_url=None, redoc_url=None, lifespan=lifespan)
_agent: Agent | None = None
_session_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
_started = time.time()


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent(settings)
        _agent.store.activity_mark_interrupted()
    return _agent


def check_token(authorization: str = Header(default="")) -> None:
    expected = f"Bearer {settings.agent_token}"
    if not hmac.compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Jeton invalide")


auth = [Depends(check_token)]


# --- Modèles ----------------------------------------------------------------------

class AskIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    session: str = Field(default="iphone", max_length=64)
    source: str = Field(default="iphone", max_length=20)
    persona: Literal["cortana", "caro"] = "cortana"


class AskOut(BaseModel):
    reply: str
    # Champs « à plat » : plus simples à lire dans l'app Raccourcis.
    action_type: str = "aucune"
    action_texte: str = ""
    action_url: str = ""
    action_date: str = ""


class TacheIn(BaseModel):
    titre: str = Field(min_length=1, max_length=500)
    echeance: str | None = None


class NoteIn(BaseModel):
    texte: str = Field(min_length=1, max_length=4000)


class BacktestIn(BaseModel):
    actif: str = Field(min_length=2, max_length=60)
    strategie: str = "tendance"
    jours: int = Field(default=365, ge=90, le=365)
    stop_pct: float = Field(default=5, ge=0.5, le=50)
    frais_pct: float = Field(default=0.2, ge=0, le=2)
    devise: str = "eur"


class OptionsIn(BaseModel):
    effort: str | None = None
    enable_web: bool | None = None
    beacon_actif: bool | None = None
    beacon_heure: str | None = None


class CleIn(BaseModel):
    nom: str
    valeur: str = Field(min_length=4, max_length=200)


# --- Pages ------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    # La page ne contient aucun secret : elle demande le jeton puis appelle l'API.
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/health")
def health() -> dict:
    return {"ok": True}


# --- Agent --------------------------------------------------------------------------

@app.post("/ask", response_model=AskOut, dependencies=auth)
def ask(body: AskIn) -> AskOut:
    text = body.text.strip()
    agent = get_agent()
    if text.lower() in {"reset", "nouvelle conversation", "oublie tout"}:
        agent.reset(body.session)
        return AskOut(reply="D'accord, nouvelle conversation.")

    store = agent.store
    act_id = store.activity_start(text, body.source, persona=body.persona)

    def fail(message: str) -> AskOut:
        store.activity_update(act_id, statut="erreur", reponse=message, fin=time.time())
        return AskOut(reply=message)

    with _session_locks[body.session]:
        try:
            result = agent.ask(text, body.session, persona=body.persona,
                               on_event=lambda e: store.activity_update(act_id, etape=e))
        except anthropic.RateLimitError:
            return fail("Trop de demandes en ce moment, réessaie dans une minute.")
        except anthropic.AuthenticationError:
            logging.exception("clé API invalide")
            return fail("Ma clé API Anthropic est invalide. Vérifie la configuration du serveur.")
        except anthropic.APIStatusError as e:
            logging.exception("erreur API")
            return fail(f"Erreur du service Claude ({e.status_code}). Réessaie plus tard.")
        except anthropic.APIConnectionError:
            logging.exception("connexion API")
            return fail("Je n'arrive pas à joindre Claude. Vérifie la connexion du serveur.")
        except Exception:  # noqa: BLE001 - on veut toujours répondre quelque chose à Siri
            logging.exception("erreur inattendue")
            return fail("Une erreur inattendue s'est produite sur le serveur.")

    _cache.pop("cerveau", None)  # la mémoire a pu changer
    statut = "refus" if result.stop_reason == "refusal" else "termine"
    store.activity_update(act_id, statut=statut, reponse=result.text,
                          action=result.iphone_action, fin=time.time())

    out = AskOut(reply=result.text)
    if a := result.iphone_action:
        out.action_type = a["type"]
        out.action_texte = a["texte"]
        out.action_url = a["url"]
        out.action_date = a["date"]
    return out


@app.post("/reset", dependencies=auth)
def reset(session: str = "iphone") -> dict:
    get_agent().reset(session)
    return {"ok": True}


# --- API du tableau de bord ------------------------------------------------------------

_cache: dict[str, tuple[float, object]] = {}
_ping_en_cours = threading.Event()


def _en_cache(cle: str, duree: float, calcul):
    t, v = _cache.get(cle, (0.0, None))
    if time.time() - t > duree:
        v = calcul()
        _cache[cle] = (time.time(), v)
    return v


def _ping_coingecko() -> None:
    """Vérifie CoinGecko en arrière-plan (au plus une fois par minute)."""
    if _ping_en_cours.is_set():
        return
    _ping_en_cours.set()

    def run() -> None:
        try:
            r = httpx.get("https://api.coingecko.com/api/v3/ping", timeout=8)
            etat.signaler("coingecko", r.status_code == 200,
                          "Joignable" if r.status_code == 200 else f"HTTP {r.status_code}")
        except httpx.HTTPError as e:
            etat.signaler("coingecko", False, type(e).__name__)
        finally:
            _ping_en_cours.clear()

    threading.Thread(target=run, daemon=True).start()


def _connexions(agent: Agent, activite: list[dict]) -> list[dict]:
    e = etat.lire()
    _en_cache("ping", 60, lambda: _ping_coingecko() or True)

    def statut(cle: str, defaut: str = "inconnu") -> str:
        if cle not in e:
            return defaut
        return "ok" if e[cle].get("ok") else "erreur"

    cle_api = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    dernier_iphone = next((a["debut"] for a in activite if a["source"] == "iphone"), None)
    opts = agent.options()
    cerveau = agent.cerveau
    out = [
        {"id": "claude", "nom": "Claude (cerveau de Jarvis)",
         "statut": statut("claude", "ok" if cle_api else "erreur"),
         "detail": e.get("claude", {}).get("detail") or ("Clé API configurée" if cle_api else "ANTHROPIC_API_KEY manquante"),
         "dernier_ok": e.get("claude", {}).get("dernier_ok")},
        {"id": "coingecko", "nom": "CoinGecko (prix et historique)", "statut": statut("coingecko"),
         "detail": e.get("coingecko", {}).get("detail", "Vérification…"),
         "dernier_ok": e.get("coingecko", {}).get("dernier_ok")},
        {"id": "web", "nom": "Recherche web", "statut": "ok" if opts["enable_web"] else "off",
         "detail": "Activée" if opts["enable_web"] else "Désactivée dans les options", "dernier_ok": None},
        {"id": "memoire", "nom": "Cerveau (mémoire git)",
         "statut": ("off" if not cerveau else statut("memoire", "ok") if cerveau.disponible else "erreur"),
         "detail": ("AGENT_CERVEAU_DIR non défini" if not cerveau else
                    e.get("memoire", {}).get("detail") or (
                        f"{cerveau.racine.name} · {'push auto' if cerveau.pousser else 'commit local'}"
                        if cerveau.disponible else f"Dossier introuvable : {cerveau.racine}")),
         "dernier_ok": e.get("memoire", {}).get("dernier_ok")},
        *[{"id": sid, "nom": nom, "statut": statut(sid), "detail": e.get(sid, {}).get("detail") or attente,
           "dernier_ok": e.get(sid, {}).get("dernier_ok")}
          for sid, nom, attente in (
              ("coinbase", "Coinbase (prix de secours)", "Utilisé seulement si CoinGecko tombe"),
              ("stooq", "Stooq (bourses, or, pétrole) · LEDGER, VAULT", "Pas encore utilisé"),
              ("frankfurter", "Frankfurter (devises) · LEDGER", "Pas encore utilisé"),
              ("mempool", "mempool.space (Bitcoin) · ORCA", "Pas encore utilisé"),
              ("ntfy", "ntfy (notifications iPhone) · BEACON", "Prêt : abonne-toi au sujet dans l'app ntfy"))],
        {"id": "etherscan", "nom": "Etherscan (Ethereum) · ORCA",
         "statut": statut("etherscan", "ok") if agent.cles.get("ETHERSCAN_API_KEY") else "off",
         "detail": e.get("etherscan", {}).get("detail") or (
             "Clé configurée" if agent.cles.get("ETHERSCAN_API_KEY") else "Clé à coller dans Clés API (gratuite)"),
         "dernier_ok": e.get("etherscan", {}).get("dernier_ok")},
        {"id": "iphone", "nom": "iPhone (Raccourci Siri)", "statut": "ok" if dernier_iphone else "inconnu",
         "detail": "Dernière demande reçue" if dernier_iphone else "Aucune demande reçue de l'iPhone pour l'instant",
         "dernier_ok": dernier_iphone},
    ]
    return out


@app.get("/api/state", dependencies=auth)
def state() -> dict:
    agent = get_agent()
    activite = agent.store.activity_list(50)
    cerveau = _en_cache("cerveau", 10, lambda: agent.cerveau.resume() if agent.cerveau else {"disponible": False})
    return {
        "activite": activite,
        "agents": agents_pour_page(agent.cles),
        "cles": agent.cles.statut(),
        "personas": list(PERSONAS.values()),
        "groupes": GROUPES,
        "caro_catalogue": CARO_CATALOGUE,
        "taches": agent.store.list_items("taches"),
        "notes": agent.store.list_items("notes")[::-1],
        "backtests": agent.store.list_items("backtests")[::-1][:12],
        "strategies": STRATEGIES,
        "cerveau": cerveau,
        "connexions": _connexions(agent, activite),
        "options": agent.options(),
        "efforts": list(EFFORTS),
        "capacites": CAPACITES,
        "demarre_depuis": _started,
    }


@app.post("/api/backtests", dependencies=auth)
def backtest_lancer(body: BacktestIn) -> dict:
    agent = get_agent()
    store = agent.store
    nom = STRATEGIES.get(body.strategie, {}).get("nom", body.strategie)
    act_id = store.activity_start(f"Backtest {nom} sur {body.actif} ({body.jours} j)", "web", persona="cortana")
    store.activity_update(act_id, etape={"outil": "backtest", "agent": "sol_paper", "entree": body.model_dump(),
                                         "erreur": False, "resultat": ""})
    ctx = ToolContext(store, settings.timezone, cerveau=agent.cerveau)
    try:
        res = lancer_backtest(ctx, body.model_dump())
    except (ToolError, httpx.HTTPError) as e:
        if isinstance(e, httpx.HTTPError):
            etat.signaler("coingecko", False, str(e)[:150])
        store.activity_update(act_id, statut="erreur", reponse=str(e), fin=time.time())
        raise HTTPException(400, str(e)) from e
    finally:
        ctx.http.close()
    store.activity_update(
        act_id, statut="termine", fin=time.time(),
        reponse=(f"{res['rendement_pct']:+.1f} % (acheter et garder {res['buy_hold_pct']:+.1f} %), "
                 f"pire chute {res['pire_chute_pct']:.1f} %, {res['nb_trades']} trades."))
    _cache.pop("cerveau", None)
    return res


@app.post("/api/taches", dependencies=auth)
def tache_ajouter(body: TacheIn) -> dict:
    return get_agent().store.add_item("taches", titre=body.titre, echeance=body.echeance, faite=False)


@app.post("/api/taches/{item_id}/basculer", dependencies=auth)
def tache_basculer(item_id: str) -> dict:
    store = get_agent().store
    tache = next((t for t in store.list_items("taches") if t["id"] == item_id), None)
    if tache is None:
        raise HTTPException(404, "Tâche introuvable")
    return store.update_item("taches", item_id, faite=not tache.get("faite"))


@app.delete("/api/taches/{item_id}", dependencies=auth)
def tache_supprimer(item_id: str) -> dict:
    if not get_agent().store.delete_item("taches", item_id):
        raise HTTPException(404, "Tâche introuvable")
    return {"ok": True}


@app.post("/api/notes", dependencies=auth)
def note_ajouter(body: NoteIn) -> dict:
    return get_agent().store.add_item("notes", texte=body.texte)


@app.delete("/api/notes/{item_id}", dependencies=auth)
def note_supprimer(item_id: str) -> dict:
    if not get_agent().store.delete_item("notes", item_id):
        raise HTTPException(404, "Note introuvable")
    return {"ok": True}


@app.post("/api/options", dependencies=auth)
def options(body: OptionsIn) -> dict:
    try:
        return get_agent().set_options(**body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# --- Coffre à clés et BEACON ----------------------------------------------------------

@app.post("/api/cles", dependencies=auth)
def cle_definir(body: CleIn) -> list[dict]:
    if body.nom not in CLES:
        raise HTTPException(400, "Clé inconnue")
    try:
        get_agent().cles.definir(body.nom, body.valeur)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return get_agent().cles.statut()


@app.delete("/api/cles/{nom}", dependencies=auth)
def cle_supprimer(nom: str) -> list[dict]:
    if nom not in CLES:
        raise HTTPException(404, "Clé inconnue")
    agent = get_agent()
    agent.cles.supprimer(nom)
    agent.cles.generer_auto()  # un sujet ntfy supprimé est aussitôt recréé (nouveau sujet)
    return agent.cles.statut()


@app.post("/api/beacon/test", dependencies=auth)
def beacon_test() -> dict:
    try:
        return {"ok": True, "texte": envoyer_rapport(get_agent())}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Envoi impossible : {e}") from e
