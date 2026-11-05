"""Configuration lue depuis les variables d'environnement (ou un fichier .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Charge un fichier .env simple (CLE=valeur) sans dépendance externe."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


ROOT = Path(__file__).resolve().parent.parent
_load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    agent_token: str
    model: str
    effort: str
    data_dir: Path
    session_ttl_hours: float
    timezone: str
    max_tool_rounds: int
    enable_web: bool
    fallbacks: bool
    cerveau_dir: Path | None
    cerveau_push: bool
    fournisseur: str          # "ollama" (libre, gratuit) ou "anthropic" (Claude, clé payante)
    ollama_url: str
    searxng_url: str
    atelier_dir: Path         # le dossier de création de Jarvis
    modele_leger: str         # modèle plus petit pour Caro et les spécialistes ("" = le même)
    historique_max: int       # messages gardés en contexte avec Ollama (vitesse, énergie)
    kiwix_url: str            # Wikipédia hors ligne (kiwix-serve) ; vide = pas installé


def load_settings() -> Settings:
    fournisseur = os.environ.get("AGENT_FOURNISSEUR", "ollama").lower()
    return Settings(
        agent_token=os.environ.get("AGENT_TOKEN", ""),
        model=os.environ.get("AGENT_MODEL", "qwen3:8b" if fournisseur == "ollama" else "claude-opus-5-5"),
        effort=os.environ.get("AGENT_EFFORT", "low"),
        data_dir=Path(os.environ.get("AGENT_DATA_DIR", ROOT / "data")),
        session_ttl_hours=float(os.environ.get("AGENT_SESSION_TTL_HOURS", "6")),
        timezone=os.environ.get("AGENT_TIMEZONE", "Europe/Paris"),
        max_tool_rounds=int(os.environ.get("AGENT_MAX_TOOL_ROUNDS", "12")),
        enable_web=os.environ.get("AGENT_ENABLE_WEB", "1") != "0",
        fallbacks=os.environ.get("AGENT_FALLBACKS", "1") != "0",
        cerveau_dir=Path(os.environ["AGENT_CERVEAU_DIR"]).expanduser() if os.environ.get("AGENT_CERVEAU_DIR") else None,
        cerveau_push=os.environ.get("AGENT_CERVEAU_PUSH", "1") != "0",
        fournisseur=fournisseur,
        ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        searxng_url=os.environ.get("SEARXNG_URL", "").rstrip("/"),
        atelier_dir=Path(os.environ.get("AGENT_ATELIER", Path.home() / "Jarvis")).expanduser(),
        modele_leger=os.environ.get("AGENT_MODELE_LEGER", ""),
        historique_max=int(os.environ.get("AGENT_HISTORIQUE_MAX", "24")),
        kiwix_url=os.environ.get("KIWIX_URL", "").rstrip("/"),
    )
