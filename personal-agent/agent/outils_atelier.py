"""Outils de création, de recherche web libre et d'action (avec confirmation)."""

from __future__ import annotations

import json
from typing import Callable

from . import web
from .atelier import AtelierErreur


class ActionErreur(Exception):
    pass


def _atelier(ctx):
    if not getattr(ctx, "atelier", None):
        raise ActionErreur("L'atelier n'est pas disponible.")
    return ctx.atelier


def _ecriture_permise(ctx):
    if ctx.lecture_seule:
        raise ActionErreur("Caro ne crée rien et n'exécute rien : demande à Cortana.")


def _lien(rel: str) -> str:
    return f"/atelier/{rel}"


def recherche_web(ctx, args: dict) -> str:
    q = str(args.get("requete") or "").strip()
    if not q:
        raise ActionErreur("Paramètre 'requete' manquant.")
    res = web.rechercher(ctx.http, getattr(ctx, "searxng_url", ""), q, int(args.get("nombre") or 6))
    if not res:
        return "Aucun résultat. Reformule la recherche avec d'autres mots."
    return json.dumps(res, ensure_ascii=False)


def lire_page(ctx, args: dict) -> str:
    try:
        return web.lire(ctx.http, str(args.get("url") or ""))
    except web.WebErreur as e:
        raise ActionErreur(str(e)) from e


def atelier_ecrire(ctx, args: dict) -> str:
    _ecriture_permise(ctx)
    a = _atelier(ctx)
    chemin, contenu = str(args.get("chemin") or ""), str(args.get("contenu") or "")
    if not chemin:
        raise ActionErreur("Paramètre 'chemin' manquant.")
    if a.est_dans_atelier(chemin):
        rel = a.ecrire(chemin, contenu)
        return f"Écrit : {rel} (lien : {_lien(rel)}). Pense à vérifier le fichier s'il s'agit de code."
    d = a.demander("ecrire", {"chemin": chemin, "contenu": contenu}, str(args.get("raison") or ""))
    return (f"Ce fichier est hors de l'atelier : demande d'autorisation n° {d['id']} créée. "
            "Rien n'est écrit avant que le propriétaire touche « Autoriser » dans la page Jarvis.")


def atelier_lire(ctx, args: dict) -> str:
    return _atelier(ctx).lire(str(args.get("chemin") or ""))


def atelier_lister(ctx, args: dict) -> str:
    return json.dumps(_atelier(ctx).lister(str(args.get("dossier") or ""), 60), ensure_ascii=False)


def creer_document(ctx, args: dict) -> str:
    _ecriture_permise(ctx)
    rel = _atelier(ctx).creer_document(str(args.get("nom") or ""), str(args.get("titre") or ""),
                                       str(args.get("contenu") or ""), str(args.get("format") or "docx"))
    return f"Document créé : {rel} (lien : {_lien(rel)})."


def creer_tableur(ctx, args: dict) -> str:
    _ecriture_permise(ctx)
    rel = _atelier(ctx).creer_tableur(str(args.get("nom") or ""), args.get("feuilles") or [])
    return f"Tableur créé : {rel} (lien : {_lien(rel)})."


def creer_site(ctx, args: dict) -> str:
    _ecriture_permise(ctx)
    a = _atelier(ctx)
    fichiers = args.get("fichiers") or {}
    if isinstance(fichiers, list):  # certains modèles envoient une liste {chemin, contenu}
        fichiers = {f.get("chemin"): f.get("contenu", "") for f in fichiers if isinstance(f, dict)}
    rel = a.creer_site(str(args.get("nom") or ""), fichiers)
    verif = a.verifier(rel)
    note = "" if verif["ok"] else f" Problèmes trouvés à corriger : {verif.get('problemes') or verif.get('erreur')}."
    return f"Site créé : {rel} (aperçu : {_lien(rel)}).{note}"


def verifier_fichier(ctx, args: dict) -> str:
    return json.dumps(_atelier(ctx).verifier(str(args.get("chemin") or "")), ensure_ascii=False)


def executer_commande(ctx, args: dict) -> str:
    _ecriture_permise(ctx)
    commande = str(args.get("commande") or "").strip()
    if not commande:
        raise ActionErreur("Paramètre 'commande' manquant.")
    d = _atelier(ctx).demander("commande", {"commande": commande, "dossier": args.get("dossier") or ""},
                               str(args.get("raison") or ""))
    return (f"Demande d'autorisation n° {d['id']} créée pour : {commande}. Elle s'exécutera quand le "
            "propriétaire touchera « Autoriser » dans la page Jarvis ; le résultat sera visible avec etat_demande.")


def etat_demande(ctx, args: dict) -> str:
    did = str(args.get("id") or "")
    d = next((x for x in ctx.store.list_items("demandes") if x["id"] == did), None)
    if not d:
        raise ActionErreur("Demande introuvable.")
    return json.dumps({k: d[k] for k in ("id", "type", "statut", "resultat")}, ensure_ascii=False)


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


S = {"type": "string"}
OUTILS_ATELIER: list[tuple[dict, Callable]] = [
    ({"name": "recherche_web", "description": "Cherche sur le web (SearXNG libre, DuckDuckGo en secours). "
      "Renvoie titres, adresses et extraits ; lis ensuite les pages utiles avec lire_page.",
      "input_schema": _obj({"requete": S, "nombre": {"type": "integer"}}, ["requete"])}, recherche_web),
    ({"name": "lire_page", "description": "Lit le texte d'une page web publique (adresse http/https).",
      "input_schema": _obj({"url": S}, ["url"])}, lire_page),
    ({"name": "creer_document", "description": "Crée un vrai document Word (docx), PDF ou Markdown dans l'atelier. "
      "contenu en Markdown simple : # titres, - puces, 1. listes, **gras**.",
      "input_schema": _obj({"nom": S, "titre": S, "contenu": S,
                            "format": {"type": "string", "enum": ["docx", "pdf", "md"]}}, ["titre", "contenu"])},
     creer_document),
    ({"name": "creer_tableur", "description": "Crée un fichier Excel (xlsx) : feuilles avec colonnes et lignes. "
      "Une cellule qui commence par = est une formule. totaux=true ajoute une ligne de totaux.",
      "input_schema": _obj({"nom": S, "feuilles": {"type": "array", "items": {"type": "object", "properties": {
          "nom": S, "colonnes": {"type": "array", "items": S}, "lignes": {"type": "array", "items": {"type": "array"}},
          "totaux": {"type": "boolean"}}, "required": ["colonnes", "lignes"]}}}, ["feuilles"])}, creer_tableur),
    ({"name": "creer_site", "description": "Crée un site ou une appli web dans l'atelier (index.html obligatoire, "
      "plus CSS/JS si besoin). Le site est vérifié automatiquement et visible dans la page Jarvis.",
      "input_schema": _obj({"nom": S, "fichiers": {"type": "object", "description": "chemin → contenu",
                                                   "additionalProperties": S}}, ["nom", "fichiers"])}, creer_site),
    ({"name": "atelier_ecrire", "description": "Écrit un fichier texte (code, script, notes, CSV…). Chemin relatif = "
      "dans l'atelier, écrit tout de suite. Chemin absolu hors de l'atelier = demande d'autorisation.",
      "input_schema": _obj({"chemin": S, "contenu": S, "raison": S}, ["chemin", "contenu"])}, atelier_ecrire),
    ({"name": "atelier_lire", "description": "Lit un fichier de l'atelier.",
      "input_schema": _obj({"chemin": S}, ["chemin"])}, atelier_lire),
    ({"name": "atelier_lister", "description": "Liste les fichiers de l'atelier (les plus récents d'abord).",
      "input_schema": _obj({"dossier": S}, [])}, atelier_lister),
    ({"name": "verifier_fichier", "description": "Vérifie un fichier créé (Python, JavaScript, JSON, HTML) et "
      "renvoie les erreurs à corriger. À faire après chaque création de code ; corrige jusqu'à ok=true.",
      "input_schema": _obj({"chemin": S}, ["chemin"])}, verifier_fichier),
    ({"name": "executer_commande", "description": "Demande à exécuter une commande sur la machine (installer, "
      "lancer un script, tester). Ne s'exécute qu'après l'autorisation du propriétaire dans la page.",
      "input_schema": _obj({"commande": S, "dossier": S, "raison": S}, ["commande", "raison"])}, executer_commande),
    ({"name": "etat_demande", "description": "Statut et résultat d'une demande d'autorisation.",
      "input_schema": _obj({"id": S}, ["id"])}, etat_demande),
]

ERREURS = (ActionErreur, AtelierErreur)
