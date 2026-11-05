"""Lien avec le Cerveau : la mémoire à long terme du dépôt `cerveaux-`.

Jarvis lit la doctrine, le profil et les leçons avant de répondre, et écrit dans le
journal, les leçons et les prédictions au format exact du dépôt, puis enregistre
(commit) et pousse avec git, en arrière-plan.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import subprocess
import threading
import time
from pathlib import Path

from . import etat

log = logging.getLogger("cerveau")

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


class CerveauErreur(Exception):
    pass


class Cerveau:
    def __init__(self, racine: Path, pousser: bool = True, timezone: str = "Europe/Paris") -> None:
        self.racine = racine.resolve()
        self.memoire = self.racine / "memoire"
        self.pousser = pousser
        self.timezone = timezone
        self._lock = threading.RLock()
        self._git_lock = threading.Lock()
        self._derniere_synchro = 0.0
        self._messages: list[str] = []
        self._travailleur_actif = False

    # --- état ---------------------------------------------------------------------
    @property
    def disponible(self) -> bool:
        return (self.memoire / "doctrine.md").is_file()

    @property
    def est_git(self) -> bool:
        return (self.racine / ".git").exists()

    def _aujourdhui(self) -> dt.date:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo(self.timezone)).date()

    def _lire(self, rel: str) -> str:
        p = self.memoire / rel
        return p.read_text(encoding="utf-8") if p.is_file() else ""

    # --- lecture ------------------------------------------------------------------
    def contexte(self, limite: int = 6000) -> str:
        """Texte ajouté au prompt système : doctrine, profil, leçons."""
        if not self.disponible:
            return ""
        parts = []
        for titre, rel in (("DOCTRINE", "doctrine.md"), ("PROFIL DU PROPRIÉTAIRE", "profil.md"),
                           ("LEÇONS (règles tirées des erreurs passées, prioritaires)", "lecons.md")):
            texte = self._lire(rel).strip()
            if texte:
                parts.append(f"## {titre}\n{texte[:limite]}")
        return "\n\n".join(parts)

    def fichiers(self) -> list[str]:
        if not self.disponible:
            return []
        return sorted(str(p.relative_to(self.memoire)) for p in self.memoire.rglob("*.md"))

    def lire(self, rel: str) -> str:
        cible = (self.memoire / rel).resolve()
        if self.memoire not in cible.parents or cible.suffix != ".md" or not cible.is_file():
            raise CerveauErreur(f"Fichier inconnu. Disponibles : {', '.join(self.fichiers())}")
        return cible.read_text(encoding="utf-8")[:12000]

    # --- écriture -------------------------------------------------------------------
    def noter_journal(self, titre: str, tache: str, resultat: str, lecon: str = "aucune") -> str:
        jour = self._aujourdhui()
        rel = f"journal/{jour:%Y-%m}.md"
        with self._lock:
            p = self.memoire / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            texte = p.read_text(encoding="utf-8") if p.is_file() else \
                f"# Journal · {MOIS[jour.month - 1]} {jour.year}\n"
            entree = (f"\n## {jour:%Y-%m-%d} · {titre.strip()}\n- Tâche : {tache.strip()}\n"
                      f"- Résultat : {resultat.strip()}\n- Leçon : {lecon.strip() or 'aucune'}\n")
            p.write_text(texte.rstrip("\n") + "\n" + entree, encoding="utf-8")
        self.enregistrer(f"jarvis: journal · {titre.strip()[:50]}")
        return f"Noté dans memoire/{rel}."

    def ajouter_lecon(self, categorie: str, ce_qui_sest_passe: str, pourquoi: str, regle: str) -> str:
        with self._lock:
            p = self.memoire / "lecons.md"
            texte = p.read_text(encoding="utf-8") if p.is_file() else "# Leçons\n"
            numeros = [int(n) for n in re.findall(r"^## L-(\d+)", texte, flags=re.M)]
            num = f"L-{(max(numeros) + 1 if numeros else 1):03d}"
            entree = (f"\n## {num} · {self._aujourdhui():%Y-%m-%d} · {categorie.strip()}\n"
                      f"- Ce qui s'est passé : {ce_qui_sest_passe.strip()}\n- Pourquoi : {pourquoi.strip()}\n"
                      f"- Règle : {regle.strip()}\n- Vu : 1 fois\n")
            p.write_text(texte.rstrip("\n") + "\n" + entree, encoding="utf-8")
        self.enregistrer(f"jarvis: leçon {num}")
        return f"Leçon {num} ajoutée."

    def enregistrer_prediction(self, actif: str, prix: str, prediction: str, raison: str, echeance: str) -> str:
        cellules = [self._aujourdhui().isoformat(), actif, prix, prediction, raison, echeance]
        ligne = "| " + " | ".join(c.replace("|", "/").strip() for c in cellules) + " |"
        with self._lock:
            p = self.memoire / "predictions.md"
            lignes = p.read_text(encoding="utf-8").splitlines() if p.is_file() else []
            try:
                debut = next(i for i, l in enumerate(lignes) if l.strip().lower() == "## en attente")
                sep = next(i for i in range(debut, len(lignes)) if lignes[i].startswith("|---"))
            except StopIteration as e:
                raise CerveauErreur("Section « ## En attente » introuvable dans predictions.md") from e
            fin = sep + 1
            while fin < len(lignes) and lignes[fin].startswith("|"):
                fin += 1
            lignes.insert(fin, ligne)
            p.write_text("\n".join(lignes) + "\n", encoding="utf-8")
        self.enregistrer(f"jarvis: prédiction {actif}")
        return "Prédiction enregistrée (à vérifier à l'échéance)."

    # --- git ------------------------------------------------------------------------
    def _git(self, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.racine), *args], capture_output=True,
                              text=True, timeout=timeout)

    def enregistrer(self, message: str) -> None:
        """Commit (et push) de memoire/ en arrière-plan, pour ne pas retarder la réponse.

        Les écritures rapprochées sont regroupées dans un seul commit qui les cite toutes.
        """
        if not self.est_git:
            return
        with self._lock:
            self._messages.append(message)
            if self._travailleur_actif:
                return
            self._travailleur_actif = True
        threading.Thread(target=self._travailleur, daemon=True).start()

    def attendre(self, timeout: float = 30) -> None:
        """Attend la fin des enregistrements en cours (utile pour les tests)."""
        fin = time.time() + timeout
        while self._travailleur_actif and time.time() < fin:
            time.sleep(0.05)

    def _travailleur(self) -> None:
        while True:
            time.sleep(0.3)  # laisse les écritures d'une même réponse arriver
            with self._lock:
                messages, self._messages = self._messages, []
                if not messages:
                    self._travailleur_actif = False
                    return
            titre = messages[0] if len(messages) == 1 else "jarvis: " + " ; ".join(
                m.removeprefix("jarvis: ") for m in messages)
            self._commit_push(titre[:200])

    def _commit_push(self, message: str) -> None:
        with self._git_lock:
            try:
                self._git("add", "memoire")
                if self._git("diff", "--cached", "--quiet").returncode == 0:
                    return
                r = self._git("commit", "-m", message)
                if r.returncode != 0:
                    raise CerveauErreur(r.stderr.strip() or r.stdout.strip())
                if not self.pousser:
                    etat.signaler("memoire", True, "Commit local (push désactivé)")
                    return
                self._git("pull", "--rebase", "--autostash", "origin", "main", timeout=120)
                for attente in (0, 2, 4, 8, 16):
                    time.sleep(attente)
                    r = self._git("push", "origin", "HEAD:main", timeout=120)
                    if r.returncode == 0:
                        etat.signaler("memoire", True, "Mémoire poussée sur GitHub")
                        return
                raise CerveauErreur(r.stderr.strip()[:200])
            except (CerveauErreur, subprocess.SubprocessError, OSError) as e:
                log.warning("git cerveau : %s", e)
                etat.signaler("memoire", False, f"Git : {e}")

    def synchroniser(self, intervalle: float = 600) -> None:
        """Récupère les nouveautés écrites par les sessions Claude Code (au plus toutes les 10 min)."""
        if not self.est_git or time.time() - self._derniere_synchro < intervalle:
            return
        self._derniere_synchro = time.time()

        def tirer() -> None:
            with self._git_lock:
                try:
                    r = self._git("pull", "--rebase", "--autostash", "origin", "main", timeout=120)
                    etat.signaler("memoire", r.returncode == 0,
                                  "Synchronisée avec GitHub" if r.returncode == 0 else f"Pull : {r.stderr.strip()[:150]}")
                except (subprocess.SubprocessError, OSError) as e:
                    etat.signaler("memoire", False, f"Pull : {e}")

        threading.Thread(target=tirer, daemon=True).start()

    # --- résumé pour le tableau de bord -----------------------------------------------
    def resume(self) -> dict:
        if not self.disponible:
            return {"disponible": False, "racine": str(self.racine)}
        # On ignore l'exemple de format placé dans un bloc de code.
        lecons_txt = re.sub(r"```.*?```", "", self._lire("lecons.md"), flags=re.S)
        lecons = []
        for m in re.finditer(r"^## (L-\d+) · ([^·\n]+) · ([^\n]+)\n(.*?)(?=^## |\Z)", lecons_txt, re.M | re.S):
            regle = re.search(r"- Règle : (.+)", m.group(4))
            vu = re.search(r"- Vu : (\d+)", m.group(4))
            lecons.append({"id": m.group(1), "date": m.group(2).strip(), "categorie": m.group(3).strip(),
                           "regle": regle.group(1).strip() if regle else "", "vu": int(vu.group(1)) if vu else 1})

        pred = self._lire("predictions.md")
        score = {k: v.strip() for k, v in re.findall(r"^- ([^:\n]+) : (.+)$", pred.split("## En attente")[0], re.M)}
        attente = []
        if "## En attente" in pred:
            bloc = pred.split("## En attente", 1)[1].split("\n## ", 1)[0]
            for l in bloc.splitlines():
                cells = [c.strip() for c in l.strip().strip("|").split("|")]
                if l.startswith("|") and not l.startswith("|---") and cells[0] != "Date" and len(cells) >= 6:
                    attente.append(dict(zip(["date", "actif", "prix", "prediction", "raison", "echeance"], cells)))

        journal = []
        dossier = self.memoire / "journal"
        for f in sorted(dossier.glob("*.md"), reverse=True)[:2] if dossier.is_dir() else []:
            for m in re.finditer(r"^## (\S+) · ([^\n]+)\n(.*?)(?=^## |\Z)", f.read_text(encoding="utf-8"), re.M | re.S):
                res = re.search(r"- Résultat : (.+)", m.group(3))
                journal.append({"date": m.group(1), "titre": m.group(2).strip(),
                                "resultat": res.group(1).strip() if res else ""})
        journal.sort(key=lambda j: j["date"], reverse=True)

        doctrine = re.findall(r"^\d+\. \*\*(.+?)\*\*|^- (Je .+?)(?:\.|$)", self._lire("doctrine.md"), re.M)
        principes = [a or b for a, b in doctrine][:8]

        commit = {}
        if self.est_git:
            try:
                r = self._git("log", "-1", "--format=%h|%s|%ct", timeout=10)
                if r.returncode == 0 and r.stdout.count("|") >= 2:
                    h, s, t = r.stdout.strip().split("|", 2)
                    commit = {"hash": h, "message": s, "date": int(t)}
            except (subprocess.SubprocessError, OSError):
                pass

        return {"disponible": True, "racine": str(self.racine), "lecons": lecons, "score": score,
                "predictions_attente": attente, "journal": journal[:8], "principes": principes,
                "fichiers": self.fichiers(), "commit": commit, "git": self.est_git, "pousser": self.pousser}
