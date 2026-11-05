"""L'atelier de Jarvis : créer de vrais fichiers (Word, PDF, Excel, sites, code) et agir sur la machine.

Règle de pouvoir choisie par le propriétaire : « tout, avec confirmation ».
- Dans le dossier atelier (AGENT_ATELIER, par défaut ~/Jarvis) : Jarvis crée et modifie librement.
- Hors de l'atelier, et pour TOUTE commande : une demande d'autorisation est créée ; rien ne s'exécute
  avant que le propriétaire touche « Autoriser » dans la page.
"""

from __future__ import annotations

import html.parser
import json
import logging
import re
import shutil
import subprocess
import time
from pathlib import Path

logging.getLogger("fontTools").setLevel(logging.WARNING)  # la bibliothèque PDF est très bavarde

DOSSIERS = {"documents", "tableurs", "sites", "code", "fichiers", "images"}
# Polices Unicode libres (accents, €, emoji non) : installées dans l'image Docker (fonts-dejavu-core).
POLICES = [("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
           ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
           ("/Library/Fonts/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf"),
           ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf")]
MAX_TEXTE = 400_000


class AtelierErreur(Exception):
    pass


class Atelier:
    def __init__(self, racine: Path, store) -> None:
        self.racine = racine.expanduser().resolve()
        self.store = store
        for d in DOSSIERS:
            (self.racine / d).mkdir(parents=True, exist_ok=True)

    # --- chemins -----------------------------------------------------------------------
    def chemin(self, rel: str) -> Path:
        """Chemin DANS l'atelier, ou erreur (jamais de sortie par ../ ou chemin absolu)."""
        rel = (rel or "").strip().lstrip("/\\")
        p = (self.racine / rel).resolve()
        if p != self.racine and self.racine not in p.parents:
            raise AtelierErreur("Ce chemin sort de l'atelier.")
        return p

    def est_dans_atelier(self, chemin: str) -> bool:
        p = Path(chemin).expanduser()
        p = (p if p.is_absolute() else self.racine / p).resolve()
        return p == self.racine or self.racine in p.parents

    def rel(self, p: Path) -> str:
        return str(p.relative_to(self.racine))

    @staticmethod
    def nom_fichier(nom: str, defaut: str = "creation") -> str:
        nom = re.sub(r"[^\w\-. ]+", "", nom or "", flags=re.U).strip().replace(" ", "-")[:80]
        return nom or f"{defaut}-{time.strftime('%Y%m%d-%H%M%S')}"

    # --- fichiers texte ------------------------------------------------------------------
    def ecrire(self, rel: str, contenu: str) -> str:
        if len(contenu) > MAX_TEXTE:
            raise AtelierErreur("Contenu trop long (400 000 caractères maximum).")
        p = self.chemin(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(contenu, encoding="utf-8")
        return self.rel(p)

    def lire(self, rel: str, limite: int = 20000) -> str:
        p = self.chemin(rel)
        if not p.is_file():
            raise AtelierErreur(f"Fichier introuvable dans l'atelier : {rel}")
        try:
            return p.read_text(encoding="utf-8")[:limite]
        except UnicodeDecodeError as e:
            raise AtelierErreur("Fichier binaire : ouvre-le depuis la galerie de la page.") from e

    def lister(self, rel: str = "", limite: int = 200) -> list[dict]:
        base = self.chemin(rel)
        if not base.is_dir():
            raise AtelierErreur(f"Dossier introuvable : {rel}")
        fichiers = [f for f in base.rglob("*") if f.is_file() and not any(x.startswith(".") for x in f.parts)]
        fichiers.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return [{"chemin": self.rel(f), "taille": f.stat().st_size, "modifie": int(f.stat().st_mtime),
                 "type": f.suffix.lstrip(".").lower() or "fichier"} for f in fichiers[:limite]]

    # --- documents --------------------------------------------------------------------
    @staticmethod
    def _blocs(markdown: str):
        """Markdown simple → blocs (titre n, puce, paragraphe), avec **gras** dans le texte."""
        for ligne in markdown.splitlines():
            l = ligne.rstrip()
            if not l.strip():
                continue
            m = re.match(r"^(#{1,3})\s+(.*)", l)
            if m:
                yield ("titre", len(m.group(1)), m.group(2))
            elif re.match(r"^\s*[-*•]\s+", l):
                yield ("puce", 0, re.sub(r"^\s*[-*•]\s+", "", l))
            elif re.match(r"^\s*\d+[.)]\s+", l):
                yield ("numero", 0, re.sub(r"^\s*\d+[.)]\s+", "", l))
            else:
                yield ("para", 0, l.strip())

    def creer_document(self, nom: str, titre: str, contenu: str, fmt: str = "docx") -> str:
        fmt = (fmt or "docx").lower()
        nom = self.nom_fichier(nom or titre, "document")
        if fmt == "md":
            return self.ecrire(f"documents/{nom}.md", f"# {titre}\n\n{contenu}\n" if titre else contenu)
        if fmt == "docx":
            from docx import Document
            from docx.shared import Pt
            doc = Document()
            doc.styles["Normal"].font.name = "Calibri"
            doc.styles["Normal"].font.size = Pt(11)
            if titre:
                doc.add_heading(titre, 0)
            for kind, niv, texte in self._blocs(contenu):
                if kind == "titre":
                    doc.add_heading(texte, niv)
                    continue
                style = {"puce": "List Bullet", "numero": "List Number"}.get(kind)
                par = doc.add_paragraph(style=style)
                for i, morceau in enumerate(re.split(r"\*\*", texte)):
                    par.add_run(morceau).bold = bool(i % 2)
            p = self.chemin(f"documents/{nom}.docx")
            doc.save(p)
            return self.rel(p)
        if fmt == "pdf":
            from fpdf import FPDF
            pdf = FPDF(format="Letter")
            police = next(((r, g) for r, g in POLICES if Path(r).is_file() and Path(g).is_file()), None)
            if police:
                pdf.add_font("Texte", "", police[0])
                pdf.add_font("Texte", "B", police[1])
                famille = "Texte"
                sur = lambda t: "".join(c for c in t if ord(c) < 0x10000)  # noqa: E731
            else:  # repli : police de base, limitée au latin-1
                famille = "Helvetica"
                sur = lambda t: t.replace("€", "EUR").replace("’", "'").replace("œ", "oe").encode(  # noqa: E731
                    "latin-1", "replace").decode("latin-1")
            pdf.set_auto_page_break(True, 18)
            pdf.add_page()
            pdf.set_margins(20, 18, 20)
            if titre:
                pdf.set_font(famille, "B", 20)
                pdf.multi_cell(0, 10, sur(titre), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(4)
            for kind, niv, texte in self._blocs(contenu):
                texte = sur(texte.replace("**", ""))
                if kind == "titre":
                    pdf.ln(2)
                    pdf.set_font(famille, "B", {1: 16, 2: 13, 3: 12}[niv])
                    pdf.multi_cell(0, 8, texte, new_x="LMARGIN", new_y="NEXT")
                else:
                    pdf.set_font(famille, "", 11)
                    prefixe = ("•  " if police else "-  ") if kind == "puce" else ""
                    pdf.multi_cell(0, 6, prefixe + texte, new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(1.5)
            p = self.chemin(f"documents/{nom}.pdf")
            pdf.output(str(p))
            return self.rel(p)
        raise AtelierErreur("Format inconnu : docx, pdf ou md.")

    # --- tableurs ---------------------------------------------------------------------
    def creer_tableur(self, nom: str, feuilles: list[dict]) -> str:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter
        if not feuilles:
            raise AtelierErreur("Il faut au moins une feuille.")
        wb = Workbook()
        wb.remove(wb.active)
        for f in feuilles:
            ws = wb.create_sheet((f.get("nom") or "Feuille")[:31])
            colonnes = f.get("colonnes") or []
            lignes = f.get("lignes") or []
            ws.append(colonnes)
            for c in ws[1]:
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor="1F2A3C")
            for l in lignes:
                ws.append([v for v in l])
            n = len(lignes)
            if f.get("totaux") and n:
                total = ["Total"] + [""] * (len(colonnes) - 1)
                for j in range(1, len(colonnes)):
                    col = get_column_letter(j + 1)
                    if any(isinstance(l[j], (int, float)) for l in lignes if j < len(l)):
                        total[j] = f"=SUM({col}2:{col}{n + 1})"
                ws.append(total)
                for c in ws[ws.max_row]:
                    c.font = Font(bold=True)
            if colonnes:
                ws.auto_filter.ref = f"A1:{get_column_letter(len(colonnes))}{n + 1}"
                ws.freeze_panes = "A2"
            for j, col in enumerate(ws.columns, 1):
                largeur = max(len(str(c.value or "")) for c in col)
                ws.column_dimensions[get_column_letter(j)].width = min(max(10, largeur + 2), 60)
        p = self.chemin(f"tableurs/{self.nom_fichier(nom, 'tableur')}.xlsx")
        wb.save(p)
        return self.rel(p)

    # --- sites ------------------------------------------------------------------------
    def creer_site(self, nom: str, fichiers: dict[str, str]) -> str:
        if not fichiers:
            raise AtelierErreur("Aucun fichier pour le site.")
        if "index.html" not in fichiers:
            raise AtelierErreur("Le site doit avoir un fichier index.html.")
        nom = self.nom_fichier(nom, "site")
        for chemin, contenu in fichiers.items():
            self.ecrire(f"sites/{nom}/{chemin}", contenu)
        return f"sites/{nom}/index.html"

    # --- vérification (autocorrection) ---------------------------------------------------
    def verifier(self, rel: str) -> dict:
        p = self.chemin(rel)
        if not p.is_file():
            raise AtelierErreur(f"Fichier introuvable : {rel}")
        ext = p.suffix.lower()
        try:
            if ext == ".py":
                compile(p.read_text(encoding="utf-8"), str(p), "exec")
            elif ext == ".json":
                json.loads(p.read_text(encoding="utf-8"))
            elif ext in (".js", ".mjs") and shutil.which("node"):
                r = subprocess.run(["node", "--check", str(p)], capture_output=True, text=True, timeout=20)
                if r.returncode:
                    return {"ok": False, "erreur": r.stderr.strip()[-1500:]}
            elif ext in (".html", ".htm"):
                return self._verifier_html(p.read_text(encoding="utf-8"))
            else:
                return {"ok": True, "note": "Pas de vérification automatique pour ce type de fichier."}
        except SyntaxError as e:
            return {"ok": False, "erreur": f"Ligne {e.lineno} : {e.msg}"}
        except json.JSONDecodeError as e:
            return {"ok": False, "erreur": f"Ligne {e.lineno} : {e.msg}"}
        return {"ok": True}

    @staticmethod
    def _verifier_html(source: str) -> dict:
        vides = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
        pile: list[str] = []
        problemes: list[str] = []

        class P(html.parser.HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag not in vides:
                    pile.append(tag)

            def handle_endtag(self, tag):
                if tag in vides:
                    return
                if tag in pile:
                    while pile and pile[-1] != tag:
                        pile.pop()
                    pile.pop()
                else:
                    problemes.append(f"balise fermante </{tag}> sans ouverture (ligne {self.getpos()[0]})")

        P().feed(source)
        if "<!doctype" not in source[:200].lower():
            problemes.append("il manque <!doctype html> au début")
        restants = [t for t in pile if t not in ("html", "body", "head", "p", "li", "td", "tr", "th", "option")]
        if restants:
            problemes.append("balises non fermées : " + ", ".join(restants[-5:]))
        return {"ok": not problemes, "problemes": problemes} if problemes else {"ok": True}

    # --- demandes d'autorisation -----------------------------------------------------------
    def demander(self, type_: str, details: dict, raison: str) -> dict:
        return self.store.add_item("demandes", cap=100, type=type_, details=details, raison=raison,
                                   statut="en_attente", resultat=None, cree=time.time())

    def executer_demande(self, d: dict) -> dict:
        """Appelé seulement après « Autoriser » dans la page."""
        if d["type"] == "commande":
            dossier = Path(d["details"].get("dossier") or self.racine).expanduser()
            if not dossier.is_dir():
                return {"code": -1, "sortie": f"Dossier introuvable : {dossier}"}
            try:
                r = subprocess.run(d["details"]["commande"], shell=True, cwd=dossier, capture_output=True,
                                   text=True, timeout=300)
                sortie = (r.stdout + ("\n" + r.stderr if r.stderr else "")).strip()
                return {"code": r.returncode, "sortie": sortie[-6000:]}
            except subprocess.TimeoutExpired:
                return {"code": -1, "sortie": "Arrêtée après 5 minutes."}
        if d["type"] == "ecrire":
            p = Path(d["details"]["chemin"]).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(d["details"]["contenu"], encoding="utf-8")
            return {"code": 0, "sortie": f"Fichier écrit : {p}"}
        return {"code": -1, "sortie": "Type de demande inconnu."}
