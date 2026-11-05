"""Serveur HTTP de Claudia : c'est lui que ton iPhone appelle (app Raccourcis).

    POST /tache   {"texte": "...", "conversation": "optionnel"}
    En-tête       Authorization: Bearer <CLAUDIA_JETON>
    Réponse       {"reponse": "...", "conversation": "..."}
"""

from __future__ import annotations

import os
import secrets
import uuid

import anthropic
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from claudia import Claudia

JETON = os.getenv("CLAUDIA_JETON", "")
if len(JETON) < 20:
    raise SystemExit("Définis CLAUDIA_JETON (20 caractères minimum) dans claudia/.env avant de lancer le serveur.")

app = FastAPI(title="Claudia")
client = anthropic.Anthropic()
conversations: dict[str, Claudia] = {}
MAX_CONVERSATIONS = 50


def verifier_jeton(authorization: str = Header(default="")) -> None:
    attendu = f"Bearer {JETON}"
    if not secrets.compare_digest(authorization.encode(), attendu.encode()):
        raise HTTPException(status_code=401, detail="Jeton invalide")


class Tache(BaseModel):
    texte: str
    conversation: str | None = None


@app.get("/sante")
def sante() -> dict:
    return {"ok": True}


@app.post("/tache", dependencies=[Depends(verifier_jeton)])
def tache(t: Tache) -> dict:
    cle = t.conversation or uuid.uuid4().hex
    claudia = conversations.get(cle)
    if claudia is None:
        if len(conversations) >= MAX_CONVERSATIONS:
            conversations.pop(next(iter(conversations)))  # oublie la plus ancienne
        claudia = conversations[cle] = Claudia(client)
    try:
        reponse = claudia.demander(t.texte)
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=500, detail="Clé API Anthropic invalide côté serveur.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Trop de requêtes, réessaie dans une minute.")
    except anthropic.APIStatusError as erreur:
        raise HTTPException(status_code=502, detail=f"Erreur de l'API Claude : {erreur.message}")
    except anthropic.APIConnectionError:
        raise HTTPException(status_code=502, detail="Le serveur n'arrive pas à joindre l'API Claude.")
    return {"reponse": reponse, "conversation": cle}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("CLAUDIA_PORT", "8787")))
