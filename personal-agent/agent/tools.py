"""Outils que Claude peut appeler. Chaque outil = un schéma + une fonction Python."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any, Callable
from zoneinfo import ZoneInfo

import httpx

from .storage import JsonStore

COINGECKO = "https://api.coingecko.com/api/v3"


class ToolError(Exception):
    """Erreur renvoyée à Claude comme tool_result is_error=True."""


class ToolContext:
    """État partagé pendant une requête : stockage + action à exécuter sur l'iPhone."""

    def __init__(self, store: JsonStore, timezone: str, http: httpx.Client | None = None) -> None:
        self.store = store
        self.timezone = timezone
        self.http = http or httpx.Client(timeout=15)
        self.iphone_action: dict | None = None


def _req(args: dict, key: str) -> Any:
    value = args.get(key)
    if value in (None, "", []):
        raise ToolError(f"Paramètre '{key}' manquant.")
    return value


# --- Crypto -----------------------------------------------------------------

def prix_crypto(ctx: ToolContext, args: dict) -> str:
    ids = _req(args, "ids")
    if isinstance(ids, str):
        ids = [ids]
    devise = (args.get("devise") or "eur").lower()
    r = ctx.http.get(
        f"{COINGECKO}/simple/price",
        params={
            "ids": ",".join(i.strip().lower() for i in ids),
            "vs_currencies": devise,
            "include_24hr_change": "true",
            "include_market_cap": "true",
        },
    )
    r.raise_for_status()
    data = r.json()
    if not data:
        raise ToolError("Aucune crypto trouvée. Utilise les identifiants CoinGecko (ex: bitcoin, ethereum, solana).")
    return json.dumps(data, ensure_ascii=False)


def marche_crypto(ctx: ToolContext, args: dict) -> str:
    r = ctx.http.get(f"{COINGECKO}/global")
    r.raise_for_status()
    d = r.json()["data"]
    resume = {
        "capitalisation_totale_usd": d["total_market_cap"].get("usd"),
        "volume_24h_usd": d["total_volume"].get("usd"),
        "variation_cap_24h_pct": d.get("market_cap_change_percentage_24h_usd"),
        "dominance_pct": {k: round(v, 2) for k, v in list(d["market_cap_percentage"].items())[:5]},
        "nb_cryptos_actives": d.get("active_cryptocurrencies"),
    }
    return json.dumps(resume, ensure_ascii=False)


# --- Notes & tâches -----------------------------------------------------------

def note_ajouter(ctx: ToolContext, args: dict) -> str:
    item = ctx.store.add_item("notes", texte=_req(args, "texte"))
    return f"Note enregistrée (id {item['id']})."


def notes_lister(ctx: ToolContext, args: dict) -> str:
    notes = ctx.store.list_items("notes")
    return json.dumps(notes[-30:], ensure_ascii=False) if notes else "Aucune note."


def note_supprimer(ctx: ToolContext, args: dict) -> str:
    if not ctx.store.delete_item("notes", _req(args, "id")):
        raise ToolError("Note introuvable.")
    return "Note supprimée."


def tache_ajouter(ctx: ToolContext, args: dict) -> str:
    item = ctx.store.add_item(
        "taches", titre=_req(args, "titre"), echeance=args.get("echeance") or None, faite=False
    )
    return f"Tâche ajoutée (id {item['id']})."


def taches_lister(ctx: ToolContext, args: dict) -> str:
    taches = ctx.store.list_items("taches")
    if not args.get("inclure_faites"):
        taches = [t for t in taches if not t.get("faite")]
    return json.dumps(taches, ensure_ascii=False) if taches else "Aucune tâche en cours."


def tache_terminer(ctx: ToolContext, args: dict) -> str:
    if not ctx.store.update_item("taches", _req(args, "id"), faite=True):
        raise ToolError("Tâche introuvable.")
    return "Tâche marquée comme faite."


# --- Divers -------------------------------------------------------------------

def date_heure(ctx: ToolContext, args: dict) -> str:
    now = dt.datetime.now(ZoneInfo(ctx.timezone))
    return now.strftime(f"%A %d %B %Y, %H:%M ({ctx.timezone})")


ACTIONS_IPHONE = {"rappel", "ouvrir_url", "copier", "notification"}


def action_iphone(ctx: ToolContext, args: dict) -> str:
    type_ = _req(args, "type")
    if type_ not in ACTIONS_IPHONE:
        raise ToolError(f"Type inconnu. Choix : {sorted(ACTIONS_IPHONE)}")
    if type_ == "ouvrir_url" and not str(args.get("url", "")).startswith(("http://", "https://")):
        raise ToolError("Pour 'ouvrir_url', fournis une URL http(s) valide dans 'url'.")
    if type_ in ("rappel", "copier", "notification") and not args.get("texte"):
        raise ToolError(f"Pour '{type_}', fournis 'texte'.")
    ctx.iphone_action = {
        "type": type_,
        "texte": args.get("texte") or "",
        "url": args.get("url") or "",
        "date": args.get("date") or "",
    }
    return "Action programmée : l'iPhone l'exécutera à la réception de ta réponse."


# --- Déclarations envoyées à l'API ------------------------------------------------

def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


TOOLS: list[tuple[dict, Callable[[ToolContext, dict], str]]] = [
    (
        {
            "name": "prix_crypto",
            "description": "Prix actuel, variation 24h et capitalisation d'une ou plusieurs cryptos (CoinGecko).",
            "input_schema": _obj(
                {
                    "ids": {"type": "array", "items": {"type": "string"},
                            "description": "Identifiants CoinGecko, ex: ['bitcoin','ethereum']."},
                    "devise": {"type": "string", "description": "Devise de cotation, ex: eur, usd. Défaut eur."},
                },
                ["ids"],
            ),
        },
        prix_crypto,
    ),
    (
        {
            "name": "marche_crypto",
            "description": "Vue d'ensemble du marché crypto : capitalisation totale, volume, dominance BTC/ETH.",
            "input_schema": _obj({}, []),
        },
        marche_crypto,
    ),
    (
        {
            "name": "note_ajouter",
            "description": "Enregistre une note pour l'utilisateur.",
            "input_schema": _obj({"texte": {"type": "string"}}, ["texte"]),
        },
        note_ajouter,
    ),
    (
        {"name": "notes_lister", "description": "Liste les dernières notes.", "input_schema": _obj({}, [])},
        notes_lister,
    ),
    (
        {
            "name": "note_supprimer",
            "description": "Supprime une note par son id.",
            "input_schema": _obj({"id": {"type": "string"}}, ["id"]),
        },
        note_supprimer,
    ),
    (
        {
            "name": "tache_ajouter",
            "description": "Ajoute une tâche à la liste de l'utilisateur.",
            "input_schema": _obj(
                {"titre": {"type": "string"},
                 "echeance": {"type": "string", "description": "Date/heure ISO 8601 facultative."}},
                ["titre"],
            ),
        },
        tache_ajouter,
    ),
    (
        {
            "name": "taches_lister",
            "description": "Liste les tâches (en cours par défaut).",
            "input_schema": _obj({"inclure_faites": {"type": "boolean"}}, []),
        },
        taches_lister,
    ),
    (
        {
            "name": "tache_terminer",
            "description": "Marque une tâche comme faite.",
            "input_schema": _obj({"id": {"type": "string"}}, ["id"]),
        },
        tache_terminer,
    ),
    (
        {
            "name": "date_heure",
            "description": "Date et heure actuelles dans le fuseau de l'utilisateur.",
            "input_schema": _obj({}, []),
        },
        date_heure,
    ),
    (
        {
            "name": "action_iphone",
            "description": (
                "Demande à l'iPhone d'exécuter UNE action à la réception de la réponse : "
                "'rappel' (crée un rappel iOS : texte + date ISO facultative), 'ouvrir_url' (url), "
                "'copier' (copie texte dans le presse-papiers), 'notification' (affiche texte). "
                "N'utilise que si l'utilisateur le demande."
            ),
            "input_schema": _obj(
                {
                    "type": {"type": "string", "enum": sorted(ACTIONS_IPHONE)},
                    "texte": {"type": "string"},
                    "url": {"type": "string"},
                    "date": {"type": "string", "description": "ISO 8601, ex: 2026-11-06T09:00"},
                },
                ["type"],
            ),
        },
        action_iphone,
    ),
]

TOOL_SCHEMAS = [schema for schema, _ in TOOLS]
HANDLERS = {schema["name"]: fn for schema, fn in TOOLS}

SERVER_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 3},
]


def run_tool(ctx: ToolContext, name: str, args: dict) -> tuple[str, bool]:
    """Exécute un outil. Retourne (contenu, is_error)."""
    fn = HANDLERS.get(name)
    if fn is None:
        return f"Outil inconnu : {name}", True
    try:
        return fn(ctx, args or {}), False
    except ToolError as e:
        return str(e), True
    except httpx.HTTPError as e:
        return f"Erreur réseau : {e}", True


# --- Catalogue affiché dans le tableau de bord ------------------------------------
# (catégorie, titre, description, outils, exemples de phrases à dire ou toucher)
CAPACITES = [
    {"categorie": "Crypto", "titre": "Prix en direct",
     "description": "Prix, variation sur 24 h et capitalisation de n'importe quelle crypto.",
     "outils": ["prix_crypto"],
     "exemples": ["Prix du bitcoin et de l'ethereum ?", "Combien vaut Solana en dollars ?"]},
    {"categorie": "Crypto", "titre": "Santé du marché",
     "description": "Capitalisation totale, volume, dominance BTC/ETH.",
     "outils": ["marche_crypto"],
     "exemples": ["Comment va le marché crypto aujourd'hui ?", "Quelle est la dominance du bitcoin ?"]},
    {"categorie": "Organisation", "titre": "Tâches",
     "description": "Ajouter, lister et terminer des tâches, avec échéance facultative.",
     "outils": ["tache_ajouter", "taches_lister", "tache_terminer"],
     "exemples": ["Ajoute la tâche : finir le graphique RSI", "Quelles sont mes tâches ?"]},
    {"categorie": "Organisation", "titre": "Notes",
     "description": "Garder des idées et les relire plus tard.",
     "outils": ["note_ajouter", "notes_lister", "note_supprimer"],
     "exemples": ["Note : idée de wallet multi-signature", "Lis-moi mes notes"]},
    {"categorie": "iPhone", "titre": "Actions sur le téléphone",
     "description": "Créer un rappel iOS, ouvrir un lien, copier un texte, afficher une notification.",
     "outils": ["action_iphone"],
     "exemples": ["Rappelle-moi demain à 9 h d'acheter de l'ETH", "Ouvre le graphique BTC sur TradingView"]},
    {"categorie": "Recherche", "titre": "Recherche web",
     "description": "Chercher l'actualité et lire des pages web (désactivable dans Options).",
     "outils": ["web_search", "web_fetch"],
     "exemples": ["Quelles sont les dernières actus sur le minage ?", "Résume les news Ethereum de la semaine"]},
    {"categorie": "Divers", "titre": "Date et heure",
     "description": "Connaît la date et l'heure dans ton fuseau horaire.",
     "outils": ["date_heure"],
     "exemples": ["Quel jour sommes-nous ?"]},
]
