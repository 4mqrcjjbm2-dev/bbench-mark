"""Boucle agent : Claude réfléchit, appelle des outils, puis répond."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import anthropic

from .config import Settings
from .storage import JsonStore
from .tools import SERVER_TOOLS, TOOL_SCHEMAS, ToolContext, run_tool

log = logging.getLogger("agent")

# Prompt système figé (aucune date/heure dedans) pour profiter du cache de prompt.
SYSTEM_PROMPT = """Tu es l'agent personnel de l'utilisateur. Il te parle depuis son iPhone, \
le plus souvent à la voix via Siri, et ta réponse est lue à voix haute.

Règles de réponse :
- Réponds en français, de façon brève et naturelle à l'oral (1 à 4 phrases), sauf si on te demande du détail.
- Pas de Markdown, pas de listes à puces, pas d'emojis, pas d'URL longues à lire : la réponse est parlée.
- Arrondis les nombres (ex. « environ 61 200 euros, en hausse de 2,3 % sur 24 heures »).

Outils :
- Utilise les outils plutôt que de deviner : prix et marché crypto, notes, tâches, date et heure, recherche web.
- Pour les cryptos, utilise les identifiants CoinGecko (bitcoin, ethereum, solana...).
- action_iphone fait agir le téléphone (rappel, ouvrir une URL, copier, notification). \
Utilise-la seulement quand l'utilisateur demande une action sur son téléphone. Une seule action par réponse.
- Avant de créer un rappel daté, appelle date_heure pour connaître la date du jour.

Finance : donne des données et des explications neutres. Tu ne fais pas de recommandation \
personnalisée d'achat ou de vente ; rappelle brièvement les risques si on te le demande."""


@dataclass
class AgentReply:
    text: str
    iphone_action: dict | None
    stop_reason: str


def _dump(content) -> list[dict]:
    """Convertit les blocs de réponse en dicts, sans rien modifier (thinking compris)."""
    return [b.model_dump(mode="json", by_alias=True, exclude_none=True) for b in content]


def _final_text(content) -> str:
    return " ".join(b.text.strip() for b in content if getattr(b, "type", None) == "text" and b.text.strip())


class Agent:
    def __init__(self, settings: Settings, client: anthropic.Anthropic | None = None,
                 store: JsonStore | None = None) -> None:
        self.settings = settings
        self.client = client or anthropic.Anthropic()
        self.store = store or JsonStore(settings.data_dir)
        self.tools = TOOL_SCHEMAS + (SERVER_TOOLS if settings.enable_web else [])

    def _create(self, messages: list[dict]):
        kwargs: dict = dict(
            model=self.settings.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=self.tools,
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": self.settings.effort},
            cache_control={"type": "ephemeral"},
        )
        if self.settings.fallbacks:
            # Si le modèle refuse une requête par erreur, l'API la relance sur un modèle de secours.
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"
        return self.client.beta.messages.create(**kwargs)

    def ask(self, text: str, session_id: str = "iphone") -> AgentReply:
        history = self.store.load_session(session_id, self.settings.session_ttl_hours)
        messages = history + [{"role": "user", "content": text}]
        ctx = ToolContext(self.store, self.settings.timezone)
        texts: list[str] = []

        try:
            for _ in range(self.settings.max_tool_rounds):
                response = self._create(messages)
                stop = response.stop_reason

                if stop == "refusal":
                    # On ne garde pas ce tour : la conversation reste dans son état précédent.
                    return AgentReply("Désolé, je ne peux pas traiter cette demande.", None, stop)

                messages.append({"role": "assistant", "content": _dump(response.content)})
                if t := _final_text(response.content):
                    texts.append(t)

                if stop == "pause_turn":  # recherche web longue : on relance pour continuer
                    continue
                if stop != "tool_use":
                    break

                results = []
                for block in response.content:
                    if block.type == "tool_use":
                        log.info("outil %s %s", block.name, block.input)
                        content, is_error = run_tool(ctx, block.name, block.input)
                        results.append({"type": "tool_result", "tool_use_id": block.id,
                                        "content": content, "is_error": is_error})
                messages.append({"role": "user", "content": results})
            else:
                texts.append("J'ai atteint ma limite d'étapes pour cette demande.")
                stop = "max_rounds"
        finally:
            ctx.http.close()

        # On ne sauvegarde que les conversations qui se terminent par une réponse de Claude.
        if messages[-1]["role"] == "assistant":
            self.store.save_session(session_id, messages)

        reply = texts[-1] if texts else "C'est fait."
        if stop == "max_tokens":
            reply += " (réponse tronquée)"
        return AgentReply(reply, ctx.iphone_action, stop)

    def reset(self, session_id: str = "iphone") -> None:
        self.store.reset_session(session_id)
