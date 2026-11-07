"""Jarvis qui améliore son propre code, sans jamais se casser.

1. Proposer : Jarvis écrit les nouvelles versions de fichiers (agent/…, nouveaux tests) → une demande d'autorisation,
   avec le différentiel lisible dans la page. Rien n'est modifié.
2. Autoriser (le propriétaire) : copie de tout le code dans un bac d'essai, application des changements, lancement de
   TOUS les tests. Un seul test qui échoue → rien n'est appliqué, l'erreur est montrée.
3. Tests verts : sauvegarde des fichiers actuels, application, commit git local, redémarrage de Jarvis.
4. Annuler : restaure la sauvegarde et redémarre.

Garde-fous : seulement agent/** et de NOUVEAUX fichiers de tests (les tests existants ne peuvent pas être modifiés,
pour que Jarvis ne puisse pas affaiblir ses propres vérifications) ; taille limitée ; autorisation à chaque fois.
"""

from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CHEMIN_PERMIS = re.compile(r"^(agent/[\w./-]+\.(py|html|css|js|json)|tests/test_[\w-]+\.py|CHANGELOG\.md)$")
IGNORER = shutil.ignore_patterns("data", "atelier", "zim", ".venv", "venv", "__pycache__", ".pytest_cache", "*.pyc")
MAX_OCTETS = 300_000


class EvolutionErreur(Exception):
    pass


class Evolution:
    def __init__(self, source: Path, store, data_dir: Path) -> None:
        self.source = source.resolve()
        self.store = store
        self.sauvegardes = data_dir / "sauvegardes"

    # --- lire son propre code ------------------------------------------------------------
    def lister(self) -> list[str]:
        out = []
        for base in ("agent", "tests"):
            for f in sorted((self.source / base).rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    out.append(str(f.relative_to(self.source)))
        return out

    def lire(self, rel: str, debut: int = 1, lignes: int = 400) -> str:
        p = (self.source / rel).resolve()
        if self.source not in p.parents or not p.is_file():
            raise EvolutionErreur(f"Fichier introuvable dans le code de Jarvis : {rel}")
        tout = p.read_text(encoding="utf-8").splitlines()
        debut = max(1, debut)
        morceau = tout[debut - 1:debut - 1 + lignes]
        fin = debut + len(morceau) - 1
        return f"{rel} (lignes {debut}-{fin} sur {len(tout)})\n" + "\n".join(
            f"{i:>5} {l}" for i, l in enumerate(morceau, debut))

    # --- proposer ------------------------------------------------------------------------
    def verifier_fichiers(self, fichiers: dict[str, str]) -> None:
        if not fichiers:
            raise EvolutionErreur("Aucun fichier dans la proposition.")
        for rel, contenu in fichiers.items():
            if not CHEMIN_PERMIS.match(rel or "") or ".." in rel:
                raise EvolutionErreur(f"Chemin non permis : {rel}. Permis : agent/…, un NOUVEAU tests/test_….py, CHANGELOG.md.")
            if rel.startswith("tests/") and (self.source / rel).exists():
                raise EvolutionErreur(f"{rel} existe déjà : les tests existants ne se modifient pas. Ajoute un nouveau fichier de test.")
            if len(contenu.encode("utf-8")) > MAX_OCTETS:
                raise EvolutionErreur(f"{rel} est trop gros (300 ko maximum).")

    def differentiel(self, fichiers: dict[str, str], limite: int = 12000) -> tuple[str, dict]:
        morceaux, stats = [], {}
        for rel, nouveau in fichiers.items():
            p = self.source / rel
            ancien = p.read_text(encoding="utf-8").splitlines(keepends=True) if p.is_file() else []
            d = list(difflib.unified_diff(ancien, nouveau.splitlines(keepends=True), f"a/{rel}", f"b/{rel}", n=2))
            stats[rel] = {"ajouts": sum(1 for l in d if l.startswith("+") and not l.startswith("+++")),
                          "retraits": sum(1 for l in d if l.startswith("-") and not l.startswith("---")),
                          "nouveau": not p.exists()}
            morceaux.append("".join(d))
        texte = "\n".join(morceaux)
        return (texte[:limite] + ("\n… (différentiel coupé)" if len(texte) > limite else "")), stats

    def proposer(self, titre: str, raison: str, fichiers: dict[str, str]) -> dict:
        self.verifier_fichiers(fichiers)
        diff, stats = self.differentiel(fichiers)
        if not any(s["ajouts"] or s["retraits"] for s in stats.values()):
            raise EvolutionErreur("Ces fichiers sont identiques au code actuel : rien à changer.")
        return self.store.add_item("demandes", cap=100, type="evolution", raison=raison, statut="en_attente",
                                   resultat=None, cree=time.time(),
                                   details={"titre": titre, "fichiers": fichiers, "diff": diff, "stats": stats})

    # --- appliquer (après « Autoriser ») -----------------------------------------------------
    def _tests(self, dossier: Path) -> subprocess.CompletedProcess:
        env = {**os.environ, "JARVIS_SANS_PLANIFICATEUR": "1", "AGENT_HORS_LIGNE": "0", "PYTHONDONTWRITEBYTECODE": "1"}
        env.pop("AGENT_DATA_DIR", None)
        env.pop("AGENT_ATELIER", None)
        return subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"], cwd=dossier,
                              capture_output=True, text=True, timeout=900, env=env)

    def appliquer(self, d: dict) -> dict:
        fichiers = d["details"]["fichiers"]
        self.verifier_fichiers(fichiers)  # revérifié : un test créé entre-temps ne peut pas être écrasé
        with tempfile.TemporaryDirectory(prefix="jarvis-essai-") as tmp:
            essai = Path(tmp) / "code"
            shutil.copytree(self.source, essai, ignore=IGNORER)
            for rel, contenu in fichiers.items():
                (essai / rel).parent.mkdir(parents=True, exist_ok=True)
                (essai / rel).write_text(contenu, encoding="utf-8")
            try:
                r = self._tests(essai)
            except subprocess.TimeoutExpired:
                return {"code": 1, "sortie": "Tests arrêtés après 15 minutes : évolution NON appliquée."}
            if r.returncode != 0:
                return {"code": 1, "sortie": "Tests en échec : évolution NON appliquée, Jarvis est intact.\n"
                        + (r.stdout + r.stderr)[-4000:]}
        # Tests verts : sauvegarde puis application.
        sauvegarde = self.sauvegardes / d["id"]
        sauvegarde.mkdir(parents=True, exist_ok=True)
        nouveaux = []
        for rel in fichiers:
            p = self.source / rel
            if p.exists():
                (sauvegarde / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, sauvegarde / rel)
            else:
                nouveaux.append(rel)
        (sauvegarde / ".nouveaux").write_text("\n".join(nouveaux), encoding="utf-8")
        for rel, contenu in fichiers.items():
            (self.source / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.source / rel).write_text(contenu, encoding="utf-8")
        commit = self._commit(list(fichiers), f"jarvis-evolution: {d['details']['titre']}")
        resume = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "tests OK"
        return {"code": 0, "redemarrer": True, "annulable": True,
                "sortie": f"Tests : {resume}\nAppliqué ({len(fichiers)} fichier(s)).{commit}\nJarvis redémarre."}

    def annuler(self, d: dict) -> dict:
        sauvegarde = self.sauvegardes / d["id"]
        if not sauvegarde.is_dir():
            raise EvolutionErreur("Pas de sauvegarde pour cette évolution.")
        for f in sauvegarde.rglob("*"):
            if f.is_file() and f.name != ".nouveaux":
                rel = f.relative_to(sauvegarde)
                shutil.copy2(f, self.source / rel)
        marque = sauvegarde / ".nouveaux"
        for rel in (marque.read_text(encoding="utf-8").split("\n") if marque.exists() else []):
            if rel and (self.source / rel).exists():
                (self.source / rel).unlink()
        commit = self._commit(list(d["details"]["fichiers"]), f"jarvis-evolution: annulation de « {d['details']['titre']} »")
        return {"code": 0, "redemarrer": True, "annulable": False, "sortie": f"Évolution annulée.{commit}\nJarvis redémarre."}

    def _commit(self, fichiers: list[str], message: str) -> str:
        if not (self.source / ".git").exists() and not (self.source.parent / ".git").exists():
            return ""
        g = ["git", "-C", str(self.source), "-c", "user.name=Jarvis", "-c", "user.email=jarvis@local"]
        try:
            subprocess.run(g + ["add", "-A", "--", *fichiers], capture_output=True, timeout=30)
            r = subprocess.run(g + ["commit", "-q", "-m", message], capture_output=True, text=True, timeout=30)
            return " Commit git local enregistré." if r.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""
