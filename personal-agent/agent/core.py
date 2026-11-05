"""Boucle agent : Claude réfléchit, appelle des outils, puis répond."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable

import anthropic

from . import etat
from .agents_outils import SPECIALISTES
from .atelier import Atelier
from .llm import creer_client, creer_message, tokens
from .reseau import OUTILS_INTERNET, en_ligne
from .cerveau import Cerveau
from .cles import Cles
from .config import Settings
from .storage import JsonStore
from .catalogue import AGENT_PAR_OUTIL, GUIDE_APP, OUTILS_LECTURE, PERSONAS, resume_catalogue
from .tools import SERVER_TOOLS, TOOL_SCHEMAS, TOOL_SCHEMAS_CERVEAU, ToolContext, run_tool

log = logging.getLogger("agent")

# Prompt système figé (aucune date/heure dedans) pour profiter du cache de prompt.
SYSTEM_PROMPT = """Tu fais partie de Jarvis, l'écosystème d'agents personnel de l'utilisateur. Il te parle \
depuis son iPhone, le plus souvent à la voix, et ta réponse est lue à voix haute.

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

Parler québécois (VOX) : comprends les expressions du Québec (Charlevoix, Saguenay, Côte-Nord, \
Blanc-Sablon) comme « char » (voiture), « blé d'Inde », « tantôt », « icitte », « pantoute », « jaser », \
« magasiner », « dépanneur ». Réponds en français clair.

Agents : pour chaque demande, prends le chemin le plus direct et le plus sûr. Utilise l'outil de l'agent \
spécialisé (PULSE prix et tendances, LEDGER bourses et devises, VAULT matières premières, Sniper Pro lecture \
technique, SOL Paper Trader backtests, ORCA portefeuilles publics, BEACON notifications et rapport, \
consulter_specialiste pour ECHO, SILK, AURA, FESTA, FORGE, NEON, RIG, AEGIS, PRISM, Agent Pub). Appelle \
plusieurs outils en parallèle quand ils sont indépendants. Si une source ne répond pas, dis-le en une phrase \
et donne ce que tu as. Si une clé manque, dis exactement où la coller (page Jarvis, Connexions → Clés API).

Atelier (créer) : quand on te demande de créer quelque chose, crée le VRAI fichier avec creer_document \
(Word/PDF), creer_tableur (Excel), creer_site (site ou appli web) ou atelier_ecrire (code, scripts), puis \
donne son nom. Fais un travail complet et soigné du premier coup : contenu réel, pas de « à compléter ».
Meilleur chemin : avant d'agir, choisis la façon qui a le plus de chances de réussir et garde un plan B. \
Autocorrection : après avoir créé du code ou un site, appelle verifier_fichier et corrige jusqu'à ok=true. \
Si un outil échoue, lis l'erreur et corrige (3 essais au plus sur la même approche), puis passe au plan B, \
puis à une autre voie (autre outil, recherche web). Ne demande au propriétaire que le seul geste qui te manque.
Agir sur la machine : executer_commande crée une demande d'autorisation ; dis au propriétaire d'autoriser \
dans la page (section Atelier), puis consulte le résultat avec etat_demande.
Savoir : pour un fait stable (histoire, science, lieux, définitions), utilise d'abord encyclopedie (hors ligne, \
rapide, gratuit) ; le web (recherche_web puis lire_page) seulement pour l'actualité ou si l'encyclopédie ne suffit \
pas. Cite tes sources.

Finance : donne des données et des explications neutres. Tu ne fais pas de recommandation \
personnalisée d'achat ou de vente ; rappelle brièvement les risques si on te le demande.
Trading : uniquement des backtests (simulation). Tu ne passes jamais d'ordre réel et ne touches \
à aucun wallet, clé privée ou compte d'échange. Rapporte toujours la pire chute d'un backtest, pas seulement le gain."""

PERSONA_PROMPTS = {
    "cortana": """Tu es Cortana, la voix qui EXÉCUTE les tâches avec l'application Jarvis. Quand on te demande \
quelque chose, fais-le avec les outils, puis confirme en une phrase ce qui est fait. Si une demande porte \
surtout sur le fonctionnement de l'application, réponds brièvement et rappelle que Caro peut tout expliquer.""",
    "caro": """Tu es Caro, la voix québécoise qui EXPLIQUE l'application Jarvis. Tu aides à comprendre : \
ce que fait chaque section, chaque agent, où en est chacun, comment s'en servir. Parle simplement, avec \
chaleur. Tu consultes (prix, tâches, notes, mémoire, catalogue, web) mais tu ne modifies rien : si on te \
demande d'agir (créer une tâche, un rappel, une note, un backtest, écrire dans la mémoire), explique \
comment faire et dis de demander à Cortana. Ne prétends jamais qu'un agent « à bâtir » fonctionne déjà.""",
}

CERVEAU_PROMPT = """Tu es relié au Cerveau, la mémoire à long terme de ton propriétaire (dépôt git). \
Ci-dessous sa doctrine, son profil et les leçons tirées des erreurs passées : elles passent avant tes habitudes.
- Si le propriétaire te corrige (« non », « c'est faux »), ajoute une leçon avec memoire_lecon.
- Après une tâche importante (backtest, analyse, décision), note-la avec memoire_journal. \
Pas pour les petites questions.
- Pour les connaissances ou prédictions passées, utilise memoire_lire.

"""


# Demandes qui méritent le modèle renfort : créations longues ou complexes (vérifié par mots-clés, sans appel IA).
TACHE_LOURDE = re.compile(
    r"\b(site|application|appli|app web|jeu|plan d'affaires|business plan|programme complet|logiciel|"
    r"analyse (approfondie|complète|détaillée)|rapport complet|refais tout|architecture|tableau de bord complet)\b",
    re.I)


@dataclass
class AgentReply:
    text: str
    iphone_action: dict | None
    stop_reason: str
    events: list[dict] = field(default_factory=list)
    tokens: dict = field(default_factory=lambda: {"entree": 0, "sortie": 0, "appels": 0})
    modele: str = ""          # modèle réellement utilisé pour cette demande
    renfort: bool = False     # True si le modèle renfort (payant) a servi


EFFORTS = ("low", "medium", "high", "xhigh", "max")


def agent_de(outil: str, entree: dict, persona: str) -> str:
    """L'agent du Catalogue qui travaille pour cet appel (pour la Blackbox)."""
    if outil == "consulter_specialiste" and isinstance(entree, dict) and entree.get("agent") in SPECIALISTES:
        return entree["agent"]
    return AGENT_PAR_OUTIL.get(outil, persona)


def _dump(content) -> list[dict]:
    """Convertit les blocs de réponse en dicts, sans rien modifier (thinking compris)."""
    return [b.model_dump(mode="json", by_alias=True, exclude_none=True) for b in content]


def _final_text(content) -> str:
    return " ".join(b.text.strip() for b in content if getattr(b, "type", None) == "text" and b.text.strip())


class Agent:
    def __init__(self, settings: Settings, client: anthropic.Anthropic | None = None,
                 store: JsonStore | None = None) -> None:
        self.settings = settings
        self.client = client or creer_client(settings)
        self.store = store or JsonStore(settings.data_dir)
        self._tokens_specialistes = {"entree": 0, "sortie": 0}
        self.cerveau = Cerveau(settings.cerveau_dir, settings.cerveau_push, settings.timezone) \
            if settings.cerveau_dir else None
        self.atelier = Atelier(settings.atelier_dir, self.store)
        self.cles = Cles(settings.data_dir)
        self.cles.generer_auto()  # sujet ntfy : rien à faire pour le propriétaire

    def options(self) -> dict:
        """Réglages modifiables depuis le tableau de bord (sinon valeurs du .env)."""
        saved = self.store.get_options()
        return {
            "fournisseur": self.settings.fournisseur,
            "model": self.settings.model,
            "modele_leger": self.settings.modele_leger or self.settings.model,
            "effort": saved.get("effort", self.settings.effort),
            "enable_web": saved.get("enable_web", self.settings.enable_web),
            "fallbacks": self.settings.fallbacks,
            "session_ttl_hours": self.settings.session_ttl_hours,
            "timezone": self.settings.timezone,
            "modele_renfort": self.settings.modele_renfort,
            "renfort_actif": saved.get("renfort_actif", True),
            "renfort_auto": saved.get("renfort_auto", True),
            "beacon_actif": saved.get("beacon_actif", True),
            "beacon_heure": saved.get("beacon_heure", "08:00"),
        }

    def set_options(self, effort: str | None = None, enable_web: bool | None = None,
                    beacon_actif: bool | None = None, beacon_heure: str | None = None,
                    renfort_actif: bool | None = None, renfort_auto: bool | None = None) -> dict:
        changes: dict = {}
        for cle, val in (("renfort_actif", renfort_actif), ("renfort_auto", renfort_auto)):
            if val is not None:
                changes[cle] = bool(val)
        if beacon_actif is not None:
            changes["beacon_actif"] = bool(beacon_actif)
        if beacon_heure is not None:
            import re
            if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", beacon_heure):
                raise ValueError("Heure au format HH:MM, ex. 08:00")
            changes["beacon_heure"] = beacon_heure
        if effort is not None:
            if effort not in EFFORTS:
                raise ValueError(f"effort doit être l'un de {EFFORTS}")
            changes["effort"] = effort
        if enable_web is not None:
            changes["enable_web"] = bool(enable_web)
        self.store.set_options(**changes)
        return self.options()

    def _system(self, persona: str) -> list[dict]:
        blocs = [{"type": "text", "text": SYSTEM_PROMPT + "\n\n" + PERSONA_PROMPTS[persona]
                  + "\n\n## L'APPLICATION\n" + GUIDE_APP + "\n\n## LES AGENTS DU CATALOGUE\n" + resume_catalogue()}]
        if self.cerveau and self.cerveau.disponible:
            self.cerveau.synchroniser()
            blocs.append({"type": "text", "text": CERVEAU_PROMPT + self.cerveau.contexte()})
        return blocs

    def outils(self, persona: str) -> list[dict]:
        opts = self.options()
        cerveau_ok = bool(self.cerveau and self.cerveau.disponible)
        web_serveur = self.settings.fournisseur == "anthropic" and opts["enable_web"]
        tools = [t for t in TOOL_SCHEMAS
                 if opts["enable_web"] or t["name"] not in ("recherche_web", "lire_page")]
        if web_serveur:  # Claude a sa propre recherche web : pas de doublon
            tools = [t for t in tools if t["name"] not in ("recherche_web", "lire_page")]
        tools += (TOOL_SCHEMAS_CERVEAU if cerveau_ok else []) + (SERVER_TOOLS if web_serveur else [])
        if not self.settings.kiwix_url:
            tools = [t for t in tools if t["name"] != "encyclopedie"]
        if self.settings.fournisseur == "ollama" and not en_ligne():
            # Hors ligne : on ne décrit même pas au modèle les outils qui ont besoin d'Internet.
            tools = [t for t in tools if t["name"] not in OUTILS_INTERNET]
        if persona == "caro":  # Caro consulte, elle ne modifie rien
            tools = [t for t in tools if t["name"] in OUTILS_LECTURE]
        return tools

    def modele_pour(self, persona: str) -> str:
        """Caro explique et les spécialistes résument : un modèle léger suffit. Cortana crée : le principal."""
        return (self.settings.modele_leger or self.settings.model) if persona in ("caro", "specialiste") \
            else self.settings.model

    def utiliser_renfort(self, persona: str, texte: str, demande: bool = False) -> bool:
        """Le renfort (cloud, payant) seulement pour Cortana, en ligne, si configuré et activé :
        quand on le demande, ou automatiquement pour une grosse création."""
        opts = self.options()
        if not self.settings.modele_renfort or persona != "cortana" or not opts["renfort_actif"]:
            return False
        if self.settings.fournisseur == "ollama" and not en_ligne():
            return False
        return demande or (opts["renfort_auto"] and (bool(TACHE_LOURDE.search(texte)) or len(texte) > 600))

    @staticmethod
    def historique_borne(history: list[dict], maxi: int) -> list[dict]:
        """Garde les derniers échanges, en coupant juste avant une vraie question (jamais entre un appel
        d'outil et son résultat). Seulement avec Ollama : chez Claude, l'historique reste intact."""
        if len(history) <= maxi:
            return history
        for i in range(len(history) - maxi, len(history)):
            m = history[i]
            if m["role"] == "user" and isinstance(m["content"], str):
                return history[i:]
        return []

    def _create(self, messages: list[dict], persona: str, modele: str | None = None):
        opts = self.options()
        try:
            response = creer_message(self.client, self.settings, system=self._system(persona), messages=messages,
                                     tools=self.outils(persona), effort=opts["effort"],
                                     modele=modele or self.modele_pour(persona))
        except Exception as e:
            etat.signaler("claude", False, type(e).__name__)
            raise
        etat.signaler("claude", True, f"{self.settings.fournisseur} · {self.settings.model}")
        return response

    def specialiste(self, agent: str, demande: str) -> str:
        """Un agent du Catalogue répond avec son propre métier et sa recherche web (sous-agent)."""
        nom, metier = SPECIALISTES[agent]
        opts = self.options()
        system = (f"Tu es {nom}, agent de l'écosystème Jarvis : {metier}\n"
                  "Réponds en français, de façon concrète et vérifiable : chiffres, noms, dates. "
                  "Cherche sur le web quand l'information doit être récente, et cite tes sources (nom du site). "
                  "Dis clairement ce qui est incertain. Pas de conseil d'achat ou de vente financier.")
        if not opts["enable_web"]:
            tools: list[dict] = []
        elif self.settings.fournisseur == "anthropic":
            tools = SERVER_TOOLS
        else:
            tools = [t for t in TOOL_SCHEMAS if t["name"] in ("recherche_web", "lire_page")]
        messages: list[dict] = [{"role": "user", "content": demande}]
        textes: list[str] = []
        ctx = ToolContext(self.store, self.settings.timezone, searxng_url=self.settings.searxng_url,
                          lecture_seule=True)
        try:
            for _ in range(6):
                r = creer_message(self.client, self.settings, system=system, messages=messages, tools=tools,
                                  effort="low", max_tokens=8000, cache=False, modele=self.modele_pour("specialiste"))
                e_, s_ = tokens(r)
                self._tokens_specialistes["entree"] += e_
                self._tokens_specialistes["sortie"] += s_
                if r.stop_reason == "refusal":
                    return f"{nom} ne peut pas traiter cette demande."
                if t := _final_text(r.content):
                    textes.append(t)
                if r.stop_reason not in ("pause_turn", "tool_use"):
                    break
                messages.append({"role": "assistant", "content": _dump(r.content)})
                if r.stop_reason == "tool_use":
                    resultats = []
                    for b in r.content:
                        if b.type == "tool_use":
                            contenu, err = run_tool(ctx, b.name, b.input) if b.name in ("recherche_web", "lire_page") \
                                else ("Outil non disponible pour un spécialiste.", True)
                            resultats.append({"type": "tool_result", "tool_use_id": b.id, "content": contenu,
                                              "is_error": err})
                    messages.append({"role": "user", "content": resultats})
        finally:
            ctx.http.close()
        return (textes[-1] if textes else "") or f"{nom} n'a rien trouvé."

    def ask(self, text: str, session_id: str = "iphone",
            on_event: Callable[[dict], None] | None = None, persona: str = "cortana",
            renfort: bool = False) -> AgentReply:
        """on_event reçoit chaque étape (outil appelé, recherche web) au fil de l'eau.

        Chaque voix a sa propre conversation (prompt système différent), d'où la session suffixée.
        """
        if persona not in PERSONAS:
            raise ValueError(f"Voix inconnue : {persona}")
        session_id = f"{session_id}-{persona}"
        autorises = {t["name"] for t in self.outils(persona)}
        avec_renfort = self.utiliser_renfort(persona, text, renfort)
        modele = self.settings.modele_renfort if avec_renfort else self.modele_pour(persona)
        events: list[dict] = []

        def emit(event: dict) -> None:
            events.append(event)
            if on_event:
                on_event(event)

        history = self.store.load_session(session_id, self.settings.session_ttl_hours)
        if self.settings.fournisseur == "ollama":
            history = self.historique_borne(history, self.settings.historique_max)
        messages = history + [{"role": "user", "content": text}]
        conso = {"entree": 0, "sortie": 0, "appels": 0}
        self._tokens_specialistes = {"entree": 0, "sortie": 0}
        ctx = ToolContext(self.store, self.settings.timezone, cerveau=self.cerveau, cles=self.cles,
                          specialiste=self.specialiste, lecture_seule=(persona == "caro"),
                          atelier=self.atelier, searxng_url=self.settings.searxng_url,
                          kiwix_url=self.settings.kiwix_url)
        texts: list[str] = []

        try:
            for _ in range(self.settings.max_tool_rounds):
                response = self._create(messages, persona, modele)
                stop = response.stop_reason
                e_, s_ = tokens(response)
                conso["entree"] += e_
                conso["sortie"] += s_
                conso["appels"] += 1

                if stop == "refusal":
                    # On ne garde pas ce tour : la conversation reste dans son état précédent.
                    return AgentReply("Désolé, je ne peux pas traiter cette demande.", None, stop, events, conso,
                                      modele, avec_renfort)

                messages.append({"role": "assistant", "content": _dump(response.content)})
                if t := _final_text(response.content):
                    texts.append(t)
                for block in response.content:
                    if block.type == "server_tool_use":  # recherche / lecture web côté Anthropic
                        emit({"outil": block.name, "agent": agent_de(block.name, block.input, persona),
                              "entree": block.input, "erreur": False, "resultat": ""})

                if stop == "pause_turn":  # recherche web longue : on relance pour continuer
                    continue
                if stop != "tool_use":
                    break

                results = []
                for block in response.content:
                    if block.type == "tool_use":
                        log.info("[%s] outil %s %s", persona, block.name, block.input)
                        if block.name in autorises:
                            content, is_error = run_tool(ctx, block.name, block.input)
                        else:  # garde-fou : Caro ne peut pas appeler un outil qui modifie
                            content, is_error = "Outil non autorisé pour cette voix. Demande à Cortana.", True
                        emit({"outil": block.name, "agent": agent_de(block.name, block.input, persona),
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
        conso["entree"] += self._tokens_specialistes["entree"]
        conso["sortie"] += self._tokens_specialistes["sortie"]
        return AgentReply(reply, ctx.iphone_action, stop, events, conso, modele, avec_renfort)

    def reset(self, session_id: str = "iphone") -> None:
        for persona in PERSONAS:
            self.store.reset_session(f"{session_id}-{persona}")
