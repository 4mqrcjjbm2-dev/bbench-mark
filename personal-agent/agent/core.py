"""Boucle agent : Claude réfléchit, appelle des outils, puis répond."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

import anthropic

from . import etat
from .cerveau import Cerveau
from .config import Settings
from .storage import JsonStore
from .tools import AGENT_PAR_OUTIL, SERVER_TOOLS, TOOL_SCHEMAS, TOOL_SCHEMAS_CERVEAU, ToolContext, run_tool

log = logging.getLogger("agent")

# Prompt système figé (aucune date/heure dedans) pour profiter du cache de prompt.
SYSTEM_PROMPT = """Tu es Jarvis, l'agent personnel de l'utilisateur. Il te parle depuis son iPhone, \
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
personnalisée d'achat ou de vente ; rappelle brièvement les risques si on te le demande.
Trading : uniquement des backtests (simulation). Tu ne passes jamais d'ordre réel et ne touches \
à aucun wallet, clé privée ou compte d'échange. Rapporte toujours la pire chute d'un backtest, pas seulement le gain."""

CERVEAU_PROMPT = """Tu es relié au Cerveau, la mémoire à long terme de ton propriétaire (dépôt git). \
Ci-dessous sa doctrine, son profil et les leçons tirées des erreurs passées : elles passent avant tes habitudes.
- Si le propriétaire te corrige (« non », « c'est faux »), ajoute une leçon avec memoire_lecon.
- Après une tâche importante (backtest, analyse, décision), note-la avec memoire_journal. \
Pas pour les petites questions.
- Pour les connaissances ou prédictions passées, utilise memoire_lire.

"""


@dataclass
class AgentReply:
    text: str
    iphone_action: dict | None
    stop_reason: str
    events: list[dict] = field(default_factory=list)


EFFORTS = ("low", "medium", "high", "xhigh", "max")


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
        self.cerveau = Cerveau(settings.cerveau_dir, settings.cerveau_push, settings.timezone) \
            if settings.cerveau_dir else None

    def options(self) -> dict:
        """Réglages modifiables depuis le tableau de bord (sinon valeurs du .env)."""
        saved = self.store.get_options()
        return {
            "model": self.settings.model,
            "effort": saved.get("effort", self.settings.effort),
            "enable_web": saved.get("enable_web", self.settings.enable_web),
            "fallbacks": self.settings.fallbacks,
            "session_ttl_hours": self.settings.session_ttl_hours,
            "timezone": self.settings.timezone,
        }

    def set_options(self, effort: str | None = None, enable_web: bool | None = None) -> dict:
        changes: dict = {}
        if effort is not None:
            if effort not in EFFORTS:
                raise ValueError(f"effort doit être l'un de {EFFORTS}")
            changes["effort"] = effort
        if enable_web is not None:
            changes["enable_web"] = bool(enable_web)
        self.store.set_options(**changes)
        return self.options()

    def _system(self) -> list[dict]:
        blocs = [{"type": "text", "text": SYSTEM_PROMPT}]
        if self.cerveau and self.cerveau.disponible:
            self.cerveau.synchroniser()
            blocs.append({"type": "text", "text": CERVEAU_PROMPT + self.cerveau.contexte()})
        return blocs

    def _create(self, messages: list[dict]):
        opts = self.options()
        cerveau_ok = bool(self.cerveau and self.cerveau.disponible)
        kwargs: dict = dict(
            model=self.settings.model,
            max_tokens=16000,
            system=self._system(),
            tools=TOOL_SCHEMAS + (TOOL_SCHEMAS_CERVEAU if cerveau_ok else [])
            + (SERVER_TOOLS if opts["enable_web"] else []),
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": opts["effort"]},
            cache_control={"type": "ephemeral"},
        )
        if self.settings.fallbacks:
            # Si le modèle refuse une requête par erreur, l'API la relance sur un modèle de secours.
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"
        try:
            response = self.client.beta.messages.create(**kwargs)
        except Exception as e:
            etat.signaler("claude", False, type(e).__name__)
            raise
        etat.signaler("claude", True, f"{self.settings.model} · effort {opts['effort']}")
        return response

    def ask(self, text: str, session_id: str = "iphone",
            on_event: Callable[[dict], None] | None = None) -> AgentReply:
        """on_event reçoit chaque étape (outil appelé, recherche web) au fil de l'eau."""
        events: list[dict] = []

        def emit(event: dict) -> None:
            events.append(event)
            if on_event:
                on_event(event)

        history = self.store.load_session(session_id, self.settings.session_ttl_hours)
        messages = history + [{"role": "user", "content": text}]
        ctx = ToolContext(self.store, self.settings.timezone, cerveau=self.cerveau)
        texts: list[str] = []

        try:
            for _ in range(self.settings.max_tool_rounds):
                response = self._create(messages)
                stop = response.stop_reason

                if stop == "refusal":
                    # On ne garde pas ce tour : la conversation reste dans son état précédent.
                    return AgentReply("Désolé, je ne peux pas traiter cette demande.", None, stop, events)

                messages.append({"role": "assistant", "content": _dump(response.content)})
                if t := _final_text(response.content):
                    texts.append(t)
                for block in response.content:
                    if block.type == "server_tool_use":  # recherche / lecture web côté Anthropic
                        emit({"outil": block.name, "agent": AGENT_PAR_OUTIL.get(block.name, "jarvis"),
                              "entree": block.input, "erreur": False, "resultat": ""})

                if stop == "pause_turn":  # recherche web longue : on relance pour continuer
                    continue
                if stop != "tool_use":
                    break

                results = []
                for block in response.content:
                    if block.type == "tool_use":
                        log.info("outil %s %s", block.name, block.input)
                        content, is_error = run_tool(ctx, block.name, block.input)
                        emit({"outil": block.name, "agent": AGENT_PAR_OUTIL.get(block.name, "jarvis"),
                              "entree": block.input, "erreur": is_error, "resultat": content[:300]})
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
        return AgentReply(reply, ctx.iphone_action, stop, events)

    def reset(self, session_id: str = "iphone") -> None:
        self.store.reset_session(session_id)
