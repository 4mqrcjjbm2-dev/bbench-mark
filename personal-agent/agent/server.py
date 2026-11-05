"""Serveur HTTP appelé par le Raccourci iPhone.

Lancement : uvicorn agent.server:app --host 0.0.0.0 --port 8787
"""

from __future__ import annotations

import hmac
import logging
import threading
from collections import defaultdict

import anthropic
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .config import load_settings
from .core import Agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
settings = load_settings()

if len(settings.agent_token) < 24:
    raise RuntimeError(
        "AGENT_TOKEN absent ou trop court (24 caractères minimum). "
        "Génère-en un avec : python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

app = FastAPI(title="Agent personnel", docs_url=None, redoc_url=None)
_agent: Agent | None = None
_session_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent(settings)
    return _agent


def check_token(authorization: str = Header(default="")) -> None:
    expected = f"Bearer {settings.agent_token}"
    if not hmac.compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Jeton invalide")


class AskIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    session: str = Field(default="iphone", max_length=64)


class AskOut(BaseModel):
    reply: str
    # Champs « à plat » : plus simples à lire dans l'app Raccourcis.
    action_type: str = "aucune"
    action_texte: str = ""
    action_url: str = ""
    action_date: str = ""


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/ask", response_model=AskOut, dependencies=[Depends(check_token)])
def ask(body: AskIn) -> AskOut:
    text = body.text.strip()
    agent = get_agent()
    if text.lower() in {"reset", "nouvelle conversation", "oublie tout"}:
        agent.reset(body.session)
        return AskOut(reply="D'accord, nouvelle conversation.")

    with _session_locks[body.session]:
        try:
            result = agent.ask(text, body.session)
        except anthropic.RateLimitError:
            return AskOut(reply="Trop de demandes en ce moment, réessaie dans une minute.")
        except anthropic.AuthenticationError:
            logging.exception("clé API invalide")
            return AskOut(reply="Ma clé API Anthropic est invalide. Vérifie la configuration du serveur.")
        except anthropic.APIStatusError as e:
            logging.exception("erreur API")
            return AskOut(reply=f"Erreur du service Claude ({e.status_code}). Réessaie plus tard.")
        except anthropic.APIConnectionError:
            logging.exception("connexion API")
            return AskOut(reply="Je n'arrive pas à joindre Claude. Vérifie la connexion du serveur.")

    out = AskOut(reply=result.text)
    if a := result.iphone_action:
        out.action_type = a["type"]
        out.action_texte = a["texte"]
        out.action_url = a["url"]
        out.action_date = a["date"]
    return out


@app.post("/reset", dependencies=[Depends(check_token)])
def reset(session: str = "iphone") -> dict:
    get_agent().reset(session)
    return {"ok": True}
