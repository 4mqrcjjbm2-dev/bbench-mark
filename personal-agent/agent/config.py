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


def load_settings() -> Settings:
    return Settings(
        agent_token=os.environ.get("AGENT_TOKEN", ""),
        model=os.environ.get("AGENT_MODEL", "claude-opus-5-5"),
        effort=os.environ.get("AGENT_EFFORT", "low"),
        data_dir=Path(os.environ.get("AGENT_DATA_DIR", ROOT / "data")),
        session_ttl_hours=float(os.environ.get("AGENT_SESSION_TTL_HOURS", "6")),
        timezone=os.environ.get("AGENT_TIMEZONE", "Europe/Paris"),
        max_tool_rounds=int(os.environ.get("AGENT_MAX_TOOL_ROUNDS", "12")),
        enable_web=os.environ.get("AGENT_ENABLE_WEB", "1") != "0",
        fallbacks=os.environ.get("AGENT_FALLBACKS", "1") != "0",
    )
