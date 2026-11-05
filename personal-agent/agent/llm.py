"""Le moteur IA de Jarvis : libre (Ollama) ou Claude, derrière une seule fonction.

Ollama parle le même format que l'API Messages d'Anthropic (https://docs.ollama.com/api/anthropic-compatibility) :
on garde le SDK officiel et on change seulement l'adresse. Ce qu'Ollama ne gère pas (cache de prompt,
outils serveur, modèles de secours, réflexion adaptative, niveau d'effort) n'est envoyé qu'à Claude.
"""

from __future__ import annotations

import anthropic

from .config import Settings


def creer_client(settings: Settings) -> anthropic.Anthropic:
    if settings.fournisseur == "ollama":
        # La clé est exigée par le SDK mais ignorée par Ollama.
        return anthropic.Anthropic(base_url=settings.ollama_url, api_key="ollama", timeout=600, max_retries=1)
    return anthropic.Anthropic()


def creer_message(client, settings: Settings, *, system, messages, tools, effort: str,
                  max_tokens: int = 16000, cache: bool = True):
    """Un appel au modèle, avec seulement les paramètres que le moteur choisi comprend."""
    if settings.fournisseur == "ollama":
        texte_systeme = system if isinstance(system, str) else "\n\n".join(b["text"] for b in system)
        kwargs: dict = dict(model=settings.model, max_tokens=min(max_tokens, 8192), system=texte_systeme,
                            messages=messages)
        if tools:
            kwargs["tools"] = tools
        return client.messages.create(**kwargs)

    kwargs = dict(model=settings.model, max_tokens=max_tokens, system=system, messages=messages,
                  thinking={"type": "adaptive"}, output_config={"effort": effort})
    if tools:
        kwargs["tools"] = tools
    if cache:
        kwargs["cache_control"] = {"type": "ephemeral"}
    if settings.fallbacks:
        # Si Claude refuse une requête légitime par erreur, l'API la relance sur un modèle de secours.
        kwargs["betas"] = ["server-side-fallback-2026-07-01"]
        kwargs["fallbacks"] = "default"
    return client.beta.messages.create(**kwargs)
