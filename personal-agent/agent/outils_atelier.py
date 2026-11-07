"""Outils de création, de recherche web libre et d'action (avec confirmation)."""

from __future__ import annotations

import json
from typing import Callable

import xml.etree.ElementTree as ET

from . import savoir, web
from .atelier import AtelierErreur
from .evolution import EvolutionErreur


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


def encyclopedie(ctx, args: dict) -> str:
    """Cherche dans Wikipédia hors ligne et renvoie directement le meilleur article (un seul appel = moins de tokens)."""
    q = str(args.get("requete") or "").strip()
    if not q:
        raise ActionErreur("Paramètre 'requete' manquant.")
    try:
        res = savoir.chercher(ctx.http, getattr(ctx, "kiwix_url", ""), q, str(args.get("langue") or "fra"))
    except savoir.SavoirErreur as e:
        raise ActionErreur(str(e)) from e
    if not res:
        return "Rien trouvé dans l'encyclopédie hors ligne. Essaie un mot plus simple ou le nom exact."
    meilleur = res[0]
    try:
        texte = savoir.lire(ctx.http, meilleur["url"], int(args.get("longueur") or 4000))
    except Exception as e:  # noqa: BLE001
        texte = f"(article illisible : {e})"
    autres = "; ".join(f"{r['titre']} ({r['source']})" for r in res[1:6])
    return f"[{meilleur['source']}] {meilleur['titre']}\n{texte}\n\nAutres résultats : {autres or 'aucun'}"


def creer_image_svg(ctx, args: dict) -> str:
    _ecriture_permise(ctx)
    svg = str(args.get("svg") or "").strip()
    try:
        racine = ET.fromstring(svg)
    except ET.ParseError as e:
        raise ActionErreur(f"SVG invalide, corrige-le : {e}") from e
    if not racine.tag.endswith("svg"):
        raise ActionErreur("Le contenu doit commencer par une balise <svg>.")
    if "xmlns" not in svg[:300]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    a = _atelier(ctx)
    rel = a.ecrire(f"images/{a.nom_fichier(str(args.get('nom') or ''), 'image')}.svg", svg)
    return f"Image créée : {rel} (lien : {_lien(rel)})."


def _evolution(ctx):
    if not getattr(ctx, "evolution", None):
        raise ActionErreur("L'auto-évolution n'est pas disponible.")
    return ctx.evolution


def lister_code_jarvis(ctx, args: dict) -> str:
    return "\n".join(_evolution(ctx).lister())


def lire_code_jarvis(ctx, args: dict) -> str:
    return _evolution(ctx).lire(str(args.get("chemin") or ""), int(args.get("debut") or 1), int(args.get("lignes") or 400))


def proposer_evolution(ctx, args: dict) -> str:
    _ecriture_permise(ctx)
    fichiers = args.get("fichiers") or {}
    if isinstance(fichiers, list):
        fichiers = {f.get("chemin"): f.get("contenu", "") for f in fichiers if isinstance(f, dict)}
    d = _evolution(ctx).proposer(str(args.get("titre") or "Amélioration"), str(args.get("raison") or ""), fichiers)
    s = d["details"]["stats"]
    resume = ", ".join(f"{k} (+{v['ajouts']}/-{v['retraits']})" for k, v in s.items())
    return (f"Évolution n° {d['id']} proposée : {resume}. Rien n'est modifié. Quand le propriétaire touchera "
            "« Autoriser », TOUS les tests tourneront sur une copie ; si un seul échoue, rien ne change. "
            "Sinon : sauvegarde, application et redémarrage, avec un bouton « Annuler ».")


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
    ({"name": "encyclopedie", "description": "Wikipédia et encyclopédies HORS LIGNE (Kiwix) : cherche et renvoie "
      "directement le meilleur article. À préférer pour les faits stables (histoire, science, lieux, définitions).",
      "input_schema": _obj({"requete": S, "langue": {"type": "string", "description": "fra, eng…"},
                            "longueur": {"type": "integer"}}, ["requete"])}, encyclopedie),
    ({"name": "creer_image_svg", "description": "Crée une image vectorielle SVG (logo, icône, illustration, schéma, "
      "animation CSS ou SMIL) dans l'atelier. Fonctionne hors ligne.",
      "input_schema": _obj({"nom": S, "svg": S}, ["svg"])}, creer_image_svg),
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
    ({"name": "lister_code_jarvis", "description": "Liste les fichiers du code de Jarvis lui-même (agent/, tests/).",
      "input_schema": _obj({}, [])}, lister_code_jarvis),
    ({"name": "lire_code_jarvis", "description": "Lit un fichier du code de Jarvis, avec numéros de ligne (par morceaux).",
      "input_schema": _obj({"chemin": S, "debut": {"type": "integer"}, "lignes": {"type": "integer"}}, ["chemin"])},
     lire_code_jarvis),
    ({"name": "proposer_evolution", "description": ("Propose d'améliorer le code de Jarvis lui-même : donne le contenu "
      "COMPLET des fichiers modifiés (agent/…) et, si utile, un NOUVEAU fichier tests/test_….py qui prouve le changement. "
      "Lis d'abord le fichier avec lire_code_jarvis. Rien n'est appliqué sans l'autorisation du propriétaire ; tous les "
      "tests doivent passer."),
      "input_schema": _obj({"titre": S, "raison": S, "fichiers": {"type": "object", "description": "chemin → contenu complet",
                                                                  "additionalProperties": S}}, ["titre", "raison", "fichiers"])},
     proposer_evolution),
    ({"name": "etat_demande", "description": "Statut et résultat d'une demande d'autorisation.",
      "input_schema": _obj({"id": S}, ["id"])}, etat_demande),
]

ERREURS = (ActionErreur, AtelierErreur, EvolutionErreur)
