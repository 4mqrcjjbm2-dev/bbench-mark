"""État du serveur : de quoi la machine est capable, et quel modèle lui convient.

Sert au premier lancement (« qu'est-ce qu'il faut arranger sur l'ordinateur ? ») et au quotidien
(le modèle est-il trop lent ? le disque se remplit-il ?).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx

# Mesure de la vitesse réelle du modèle, mise à jour à chaque appel (core.Agent._create).
PERF: dict = {}


def noter_perf(modele: str, secondes: float, tokens_sortie: int) -> None:
    PERF.update(modele=modele, secondes=round(secondes, 1), quand=time.time(),
                tokens_par_seconde=round(tokens_sortie / secondes, 1) if secondes > 0 and tokens_sortie else None)


def _memoire_go() -> tuple[float | None, float | None]:
    try:
        infos = {l.split(":")[0]: int(l.split()[1]) for l in Path("/proc/meminfo").read_text().splitlines()}
        return round(infos["MemTotal"] / 1048576, 1), round(infos.get("MemAvailable", 0) / 1048576, 1)
    except (OSError, KeyError, ValueError, IndexError):
        return None, None


def _gpu() -> dict | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10)
        nom, total, utilise = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
        return {"nom": nom, "memoire_go": round(int(total) / 1024, 1), "utilisee_go": round(int(utilise) / 1024, 1)}
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def _ollama(url: str) -> dict:
    try:
        tags = httpx.get(f"{url}/api/tags", timeout=5).json().get("models", [])
        charges = httpx.get(f"{url}/api/ps", timeout=5).json().get("models", [])
        return {"joignable": True,
                "installes": [{"nom": m.get("name"), "taille_go": round((m.get("size") or 0) / 1e9, 1)} for m in tags],
                "en_memoire": [m.get("name") for m in charges]}
    except (httpx.HTTPError, ValueError):
        return {"joignable": False, "installes": [], "en_memoire": []}


def conseil_modele(ram_go: float | None, gpu: dict | None) -> str:
    """Le plus gros modèle local qui reste confortable sur cette machine."""
    if gpu and gpu["memoire_go"] >= 20:
        return "qwen3:32b"
    if gpu and gpu["memoire_go"] >= 14:
        return "qwen3:14b"
    if gpu and gpu["memoire_go"] >= 8:
        return "qwen3:8b"
    if ram_go is None:
        return "qwen3:8b"
    if ram_go >= 30:
        return "qwen3:14b"
    if ram_go >= 14:
        return "qwen3:8b"
    if ram_go >= 7:
        return "qwen3:4b"
    return "qwen3:1.7b"


def etat(settings) -> dict:
    ram, ram_libre = _memoire_go()
    gpu = _gpu()
    disque = shutil.disk_usage(settings.data_dir if Path(settings.data_dir).exists() else "/")
    olla = _ollama(settings.ollama_url) if settings.fournisseur == "ollama" else None
    conseil = conseil_modele(ram, gpu)
    remarques: list[str] = []
    if settings.fournisseur == "ollama":
        if olla and not olla["joignable"]:
            remarques.append(f"Ollama ne répond pas à {settings.ollama_url} : vérifie que le service tourne.")
        elif olla and not any(m["nom"] in (settings.model, f"{settings.model}:latest") for m in olla["installes"]) \
                and not settings.model.endswith("cloud"):
            remarques.append(f"Le modèle {settings.model} n'est pas téléchargé : « ollama pull {settings.model} ».")
        if conseil != settings.model and not settings.model.endswith("cloud"):
            remarques.append(f"Pour cette machine, le modèle conseillé est {conseil} (actuel : {settings.model}).")
    tps = PERF.get("tokens_par_seconde")
    if tps is not None and tps < 4:
        remarques.append(f"Le modèle écrit {tps} mots-jetons par seconde : c'est lent. Un modèle plus léger ou une carte graphique aiderait.")
    libre_go = round(disque.free / 1e9, 1)
    if libre_go < 15:
        remarques.append(f"Plus que {libre_go} Go libres : Wikipédia hors ligne et les modèles prennent beaucoup de place.")
    if ram_libre is not None and ram_libre < 1.5:
        remarques.append("La mémoire vive est presque pleine : choisis un modèle plus léger.")
    return {
        "processeurs": os.cpu_count(),
        "charge": round(os.getloadavg()[0], 2) if hasattr(os, "getloadavg") else None,
        "memoire_go": ram, "memoire_libre_go": ram_libre,
        "disque_total_go": round(disque.total / 1e9, 1), "disque_libre_go": libre_go,
        "gpu": gpu, "ollama": olla, "modele_conseille": conseil, "perf": dict(PERF),
        "remarques": remarques or ["Tout est en ordre."],
    }
