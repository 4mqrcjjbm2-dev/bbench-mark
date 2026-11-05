"""Claudia - agent IA personnel bâti sur l'API Claude.

Le cœur de l'agent : une boucle qui envoie la demande à Claude, exécute les
outils qu'il réclame (mémoire, heure, prix crypto) et renvoie la réponse finale.
La recherche web est un outil serveur : Anthropic l'exécute directement.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

MODELE = os.getenv("CLAUDIA_MODELE", "claude-opus-5-5")
EFFORT = os.getenv("CLAUDIA_EFFORT", "medium")  # low | medium | high | xhigh | max
FUSEAU = os.getenv("CLAUDIA_FUSEAU", "America/Toronto")
FICHIER_MEMOIRE = Path(os.getenv("CLAUDIA_MEMOIRE", Path(__file__).with_name("memoire.json")))
MAX_ETAPES = 12

SYSTEME = """Tu es Claudia, l'assistante IA personnelle de ton utilisateur.
Tu réponds en français, de façon directe et concise : tes réponses sont souvent
lues sur un iPhone ou prononcées par Siri, donc évite les longs tableaux.
Ses centres d'intérêt : cryptomonnaies, blockchain, minage, trading et
indicateurs financiers, développement de projets IA.
Utilise tes outils quand ils aident : `memoriser` pour retenir une information
durable que l'utilisateur te confie, `prix_crypto` pour les cours en direct,
`heure_actuelle` pour la date et l'heure, la recherche web pour l'actualité.
Tu ne donnes jamais de conseil financier présenté comme une certitude :
signale les risques quand tu parles d'investissement."""

OUTILS = [
    {
        "name": "memoriser",
        "description": "Enregistre durablement une information sur l'utilisateur ou ses projets "
        "(préférence, objectif, fait important). À utiliser quand l'utilisateur demande de retenir "
        "quelque chose ou partage une information utile pour plus tard.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "info": {"type": "string", "description": "L'information à retenir, en une phrase."}
            },
            "required": ["info"],
            "additionalProperties": False,
        },
    },
    {
        "name": "oublier",
        "description": "Supprime de la mémoire l'entrée dont le numéro est donné (voir la liste en mémoire).",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"numero": {"type": "integer", "description": "Numéro de l'entrée, à partir de 1."}},
            "required": ["numero"],
            "additionalProperties": False,
        },
    },
    {
        "name": "heure_actuelle",
        "description": "Donne la date et l'heure actuelles dans le fuseau de l'utilisateur.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
    {
        "name": "prix_crypto",
        "description": "Cours actuel d'une ou plusieurs cryptomonnaies (source CoinGecko), en USD et CAD, "
        "avec la variation sur 24 h. Utilise les identifiants CoinGecko : bitcoin, ethereum, solana...",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Identifiants CoinGecko, ex. [\"bitcoin\", \"ethereum\"].",
                }
            },
            "required": ["ids"],
            "additionalProperties": False,
        },
    },
    # Outil serveur : exécuté par Anthropic, rien à coder de notre côté.
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
]


# ---------- Mémoire ----------

def lire_memoire() -> list[str]:
    try:
        return json.loads(FICHIER_MEMOIRE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def ecrire_memoire(entrees: list[str]) -> None:
    FICHIER_MEMOIRE.write_text(json.dumps(entrees, ensure_ascii=False, indent=2), encoding="utf-8")


def systeme_avec_memoire() -> str:
    entrees = lire_memoire()
    if not entrees:
        return SYSTEME + "\n\nMémoire : (vide pour l'instant)"
    lignes = "\n".join(f"{i}. {e}" for i, e in enumerate(entrees, 1))
    return SYSTEME + "\n\nCe que tu sais déjà de l'utilisateur :\n" + lignes


# ---------- Outils locaux ----------

def outil_memoriser(info: str) -> str:
    entrees = lire_memoire()
    entrees.append(info.strip())
    ecrire_memoire(entrees)
    return f"Retenu (entrée n°{len(entrees)})."


def outil_oublier(numero: int) -> str:
    entrees = lire_memoire()
    if not 1 <= numero <= len(entrees):
        raise ValueError(f"Aucune entrée n°{numero} (la mémoire en contient {len(entrees)}).")
    retiree = entrees.pop(numero - 1)
    ecrire_memoire(entrees)
    return f"Oublié : {retiree}"


JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def outil_heure_actuelle() -> str:
    m = datetime.now(ZoneInfo(FUSEAU))
    return f"{JOURS[m.weekday()]} {m.day} {MOIS[m.month - 1]} {m.year}, {m:%H:%M} ({FUSEAU})"


def outil_prix_crypto(ids: list[str]) -> str:
    if not ids:
        raise ValueError("Donne au moins un identifiant de cryptomonnaie.")
    params = urllib.parse.urlencode(
        {"ids": ",".join(i.strip().lower() for i in ids), "vs_currencies": "usd,cad", "include_24hr_change": "true"}
    )
    requete = urllib.request.Request(
        f"https://api.coingecko.com/api/v3/simple/price?{params}", headers={"User-Agent": "claudia-agent"}
    )
    with urllib.request.urlopen(requete, timeout=15) as reponse:
        donnees = json.load(reponse)
    if not donnees:
        raise ValueError("Identifiants inconnus de CoinGecko (essaie par ex. 'bitcoin', 'ethereum').")
    return json.dumps(donnees)


OUTILS_LOCAUX = {
    "memoriser": outil_memoriser,
    "oublier": outil_oublier,
    "heure_actuelle": outil_heure_actuelle,
    "prix_crypto": outil_prix_crypto,
}


def executer_outil(nom: str, entree: dict) -> dict:
    """Renvoie le contenu d'un tool_result ; une erreur est signalée à Claude, pas levée."""
    fonction = OUTILS_LOCAUX.get(nom)
    if fonction is None:
        return {"content": f"Outil inconnu : {nom}", "is_error": True}
    try:
        return {"content": fonction(**entree)}
    except Exception as erreur:  # l'erreur est renvoyée à Claude, qui peut corriger sa demande
        return {"content": f"Erreur : {erreur}", "is_error": True}


# ---------- Agent ----------

class Claudia:
    """Une conversation avec Claudia. Garde l'historique entre les messages."""

    def __init__(self, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic()  # lit ANTHROPIC_API_KEY
        self.messages: list = []
        self.systeme = systeme_avec_memoire()

    def demander(self, texte: str) -> str:
        self.messages.append({"role": "user", "content": texte})

        for _ in range(MAX_ETAPES):
            reponse = self.client.beta.messages.create(
                model=MODELE,
                max_tokens=16000,
                system=self.systeme,
                tools=OUTILS,
                messages=self.messages,
                output_config={"effort": EFFORT},
                # Si un filtre de sécurité refuse à tort, l'API réessaie sur le modèle de repli conseillé.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            # On renvoie le contenu complet (blocs de réflexion compris) tel quel.
            self.messages.append({"role": "assistant", "content": reponse.content})

            if reponse.stop_reason == "refusal":
                return "Désolée, je ne peux pas traiter cette demande."
            if reponse.stop_reason == "pause_turn":  # recherche web longue : on relance
                continue
            if reponse.stop_reason != "tool_use":
                texte_final = "".join(b.text for b in reponse.content if b.type == "text").strip()
                if reponse.stop_reason == "max_tokens":
                    texte_final += "\n\n(Réponse coupée : trop longue.)"
                return texte_final or "(pas de réponse)"

            resultats = []
            for bloc in reponse.content:
                if bloc.type == "tool_use":
                    resultats.append({"type": "tool_result", "tool_use_id": bloc.id, **executer_outil(bloc.name, bloc.input)})
            self.messages.append({"role": "user", "content": resultats})

        return "J'ai atteint le nombre maximal d'étapes pour cette tâche."


def main() -> None:
    claudia = Claudia()
    print("Claudia est prête. Écris ta demande (ou « quitter »).")
    while True:
        try:
            texte = input("\nToi > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if texte.lower() in {"quitter", "exit", "quit"}:
            break
        if not texte:
            continue
        try:
            print(f"\nClaudia > {claudia.demander(texte)}")
        except anthropic.AuthenticationError:
            print("Clé API invalide : vérifie ANTHROPIC_API_KEY dans claudia/.env")
            break
        except anthropic.RateLimitError:
            print("Trop de requêtes, réessaie dans une minute.")
        except anthropic.APIConnectionError:
            print("Pas de connexion à l'API. Vérifie ta connexion Internet.")
        except anthropic.APIStatusError as erreur:
            print(f"Erreur de l'API ({erreur.status_code}) : {erreur.message}")


if __name__ == "__main__":
    main()
