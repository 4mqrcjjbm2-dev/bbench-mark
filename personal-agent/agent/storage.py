"""Stockage local en JSON : notes, tâches, sessions de conversation."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_lock = threading.RLock()


class JsonStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        (data_dir / "sessions").mkdir(parents=True, exist_ok=True)

    # --- bas niveau ---------------------------------------------------------
    def _read(self, path: Path, default: Any) -> Any:
        if not path.is_file():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default

    def _write(self, path: Path, data: Any) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)  # écriture atomique

    # --- listes (notes, tâches) --------------------------------------------
    def _list_path(self, name: str) -> Path:
        return self.data_dir / f"{name}.json"

    def add_item(self, name: str, cap: int | None = None, **fields: Any) -> dict:
        with _lock:
            items = self._read(self._list_path(name), [])
            item = {"id": uuid.uuid4().hex[:6], "cree_le": time.strftime("%Y-%m-%d %H:%M"), **fields}
            items.append(item)
            self._write(self._list_path(name), items[-cap:] if cap else items)
            return item

    def list_items(self, name: str) -> list[dict]:
        with _lock:
            return self._read(self._list_path(name), [])

    def update_item(self, name: str, item_id: str, **fields: Any) -> dict | None:
        with _lock:
            items = self._read(self._list_path(name), [])
            for item in items:
                if item["id"] == item_id:
                    item.update(fields)
                    self._write(self._list_path(name), items)
                    return item
            return None

    def delete_item(self, name: str, item_id: str) -> bool:
        with _lock:
            items = self._read(self._list_path(name), [])
            kept = [i for i in items if i["id"] != item_id]
            if len(kept) == len(items):
                return False
            self._write(self._list_path(name), kept)
            return True

    # --- options modifiables depuis le tableau de bord -----------------------
    def get_options(self) -> dict:
        with _lock:
            return self._read(self.data_dir / "options.json", {})

    def set_options(self, **changes: Any) -> None:
        with _lock:
            opts = self._read(self.data_dir / "options.json", {})
            opts.update(changes)
            self._write(self.data_dir / "options.json", opts)

    # --- journal d'activité (ce que l'agent fait, en direct) ---------------
    ACTIVITY_MAX = 200

    def activity_start(self, texte: str, source: str) -> str:
        with _lock:
            items = self._read(self._list_path("activite"), [])
            entry = {"id": uuid.uuid4().hex[:8], "debut": time.time(), "fin": None, "source": source,
                     "demande": texte, "statut": "en_cours", "etapes": [], "reponse": "", "action": None}
            items.append(entry)
            self._write(self._list_path("activite"), items[-self.ACTIVITY_MAX:])
            return entry["id"]

    def activity_update(self, entry_id: str, etape: dict | None = None, **fields: Any) -> None:
        with _lock:
            items = self._read(self._list_path("activite"), [])
            for entry in items:
                if entry["id"] == entry_id:
                    if etape:
                        entry["etapes"].append({**etape, "t": time.time()})
                    entry.update(fields)
                    break
            self._write(self._list_path("activite"), items)

    def activity_mark_interrupted(self) -> None:
        """Au démarrage : une tâche restée « en cours » a été coupée par un redémarrage."""
        with _lock:
            items = self._read(self._list_path("activite"), [])
            for entry in items:
                if entry["statut"] == "en_cours":
                    entry.update(statut="interrompu", fin=entry["debut"])
            self._write(self._list_path("activite"), items)

    def activity_list(self, limit: int = 50) -> list[dict]:
        with _lock:
            return self._read(self._list_path("activite"), [])[-limit:][::-1]

    # --- sessions -----------------------------------------------------------
    def _session_path(self, session_id: str) -> Path:
        safe = "".join(c for c in session_id if c.isalnum() or c in "-_")[:64] or "default"
        return self.data_dir / "sessions" / f"{safe}.json"

    def load_session(self, session_id: str, ttl_hours: float) -> list[dict]:
        with _lock:
            data = self._read(self._session_path(session_id), None)
            if not data:
                return []
            if time.time() - data.get("updated", 0) > ttl_hours * 3600:
                return []  # conversation trop ancienne : on repart de zéro
            return data.get("messages", [])

    def save_session(self, session_id: str, messages: list[dict]) -> None:
        with _lock:
            self._write(self._session_path(session_id), {"updated": time.time(), "messages": messages})

    def reset_session(self, session_id: str) -> None:
        with _lock:
            self._session_path(session_id).unlink(missing_ok=True)
