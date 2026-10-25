"""Moteur PDF des documents de candidature (§15-18, §47).

Portage des générateurs professionnels fournis (dossier ``exemple/``) :
fpdf2 au millimètre, positionnement absolu, mesure de hauteurs AVANT
chaque saut de page (``dry_run``), largeurs contraintes, aucun texte ne
chevauche jamais une colonne. Chaque couleur d'accent engendre sa famille
complète (bandeau sombre de la même teinte, accent vif, accent foncé).

Contenu exclusivement issu du profil validé : aucun lien, téléphone ni
compétence inventés (§47).
"""
import os
import tempfile
from datetime import date
from io import BytesIO
from typing import Any, Optional

from fpdf import FPDF

from app.services import cv_builder, uploads
from app.services.matching import compute_match
from app.services.skills_taxonomy import SkillsTaxonomy

INK = (22, 28, 38)
GRAY = (80, 95, 112)
WHITE = (255, 255, 255)
SOFTTXT = (180, 195, 210)

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

# Familles de couleurs réglées à la main : le bandeau reste très sombre,
# l'accent vif porte les règles et filets, l'accent foncé les libellés.
# Une famille PAR couleur : la différence se voit immédiatement sur le PDF.
TONE = {
    "vert": ("0B3B2A", "2FB37A", "15724E"),
    "bleu": ("0A2138", "3AA6E0", "20689E"),
    "orange": ("33200A", "F0932B", "B96A1C"),
    "bordeaux": ("2E0F16", "C2475D", "93374A"),
    "ardoise": ("1A242B", "7FA3B5", "556E7C"),
}
# Charte du modèle ATS reprise du gabarit Python de référence :
# bleu nuit (10, 17, 40), turquoise vif (43, 217, 197), turquoise foncé.
ATS_TONE = ("0A1128", "2BD9C5", "148C7D")


# ------------------------------------------------------------------ polices

_FONT_CANDIDATES = {
    "": ["arial.ttf", "Arial.ttf"],
    "B": ["arialbd.ttf", "Arialbd.ttf"],
    "I": ["ariali.ttf", "Ariali.ttf"],
    "BI": ["arialbi.ttf", "Arialbi.ttf"],
}
_SERIF_CANDIDATES = {
    "": ["times.ttf", "Times.ttf", "LiberationSerif-Regular.ttf"],
    "B": ["timesbd.ttf", "Timesbd.ttf", "LiberationSerif-Bold.ttf"],
    "I": ["timesi.ttf", "Timesi.ttf", "LiberationSerif-Italic.ttf"],
    "BI": ["timesbi.ttf", "Timesbi.ttf", "LiberationSerif-BoldItalic.ttf"],
}
_FONT_DIRS = [
    r"C:\Windows\Fonts",
    "/usr/share/fonts/truetype/msttcorefonts",
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts/truetype/dejavu",
]


def _find(candidates):
    for name in candidates:
        for d in _FONT_DIRS:
            path = os.path.join(d, name)
            if os.path.exists(path):
                return path
    return None


def _setup_fonts(p: FPDF, serif: bool = False) -> None:
    """Enregistre Arial (ou Times) si présent, sinon police cœur fpdf."""
    table = _SERIF_CANDIDATES if serif else _FONT_CANDIDATES
    fam = "TIM" if serif else "AU"
    found = True
    for style, names in table.items():
        path = _find(names)
        if path is None:
            found = False
            break
        p.add_font(fam, style, path)
    if found:
        p.fam = fam  # type: ignore[attr-defined]
    else:
        p.fam = "times" if serif else "helvetica"  # type: ignore[attr-defined]


def _t(txt) -> str:
    """Assainit pour latin-1 (polices cœur) : tirets typographiques,
    points de suspension. Aucun autre changement."""
    return (str(txt or "")
            .replace("\u2014", "-").replace("\u2013", "-")
            .replace("\u2026", "...").replace("\u2019", "'"))


# -------------------------------------------------------------------- thème

def _rgb(hexstr: str) -> tuple:
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _scale(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def _mix(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _theme(template: str, accent: Optional[str]) -> dict:
    """Famille complète de l'accent choisi (bandeau, accent vif, accent
    foncé, fonds, filets). Le modèle ATS garde sa charte tant qu'aucune
    couleur n'est demandée ; une couleur explicite est toujours honorée,
    y compris au format personnalisé #RRGGBB."""
    if cv_builder.is_custom_accent(accent):
        bright = _rgb(accent)
        band = _mix(bright, (0, 0, 0), 0.80)
        mid = _mix(bright, (0, 0, 0), 0.42)
    else:
        if template == "ats" and not accent:
            band_hex, bright_hex, mid_hex = ATS_TONE
            band, bright, mid = _rgb(band_hex), _rgb(bright_hex), _rgb(mid_hex)
        else:
            key = accent if (accent in TONE or accent in cv_builder.ACCENTS) \
                else cv_builder.DEFAULT_ACCENTS.get(template)
            if key in TONE:
                band_hex, bright_hex, mid_hex = TONE[key]
                band, bright, mid = _rgb(band_hex), _rgb(bright_hex), _rgb(mid_hex)
            elif key in cv_builder.ACCENTS:
                bright = _rgb(cv_builder.ACCENTS[key]["hex"])
                band = _mix(bright, (0, 0, 0), 0.80)
                mid = _mix(bright, (0, 0, 0), 0.42)
            else:
                band, bright, mid = _rgb(ATS_TONE[0]), _rgb(ATS_TONE[1]), _rgb(ATS_TONE[2])
    return {
        "band": band,                       # bandeau / titres : très sombre
        "bright": bright,                   # accent vif : règles et filets
        "mid": mid,                         # accent foncé : libellés
        "soft": _mix(bright, WHITE, 0.90),  # fond barre latérale
        "line": _mix(mid, WHITE, 0.62),     # filets de cadres
        "ink": INK, "gray": GRAY,
    }


# -------------------------------------------------------------------- photo

def _medaillon(user: Any, ring, bg) -> Optional[str]:
    """Photo en médaillon circulaire, anneau de la couleur d'accent
    (portage de photo_rh). None si pas de photo."""
    path = getattr(user, "photo_path", None)
    if not path:
        return None
    full = uploads.resolve(path)
    if not full.exists() or not os.access(full, os.R_OK):
        return None
    try:
        from PIL import Image, ImageDraw
        im = Image.open(full).convert("RGB")
        w, h = im.size
        s = min(w, h)
        l = (w - s) // 2
        t = max(0, int((h - s) * 0.22))
        im = im.crop((l, t, l + s, t + s)).resize((520, 520), Image.LANCZOS)
        mask = Image.new("L", (520, 520), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 520, 520), fill=255)
        b = 12
        tot = 520 + b * 2
        fin = Image.new("RGB", (tot, tot), tuple(bg))
        ImageDraw.Draw(fin).ellipse((0, 0, tot - 1, tot - 1), fill=tuple(ring))
        fin.paste(im, (b, b), mask)
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        fin.save(tmp)
        return tmp
    except Exception:
        return None


# ----------------------------------------------------------------- données

def _level(skill: dict) -> str:
    return cv_builder.PROFICIENCY_LABELS.get(skill.get("proficiency", ""), "")


def _is_soft(skill: dict) -> bool:
    cat = (skill.get("category") or "").lower()
    return "soft" in cat or "humaine" in cat


def _ordered_skills(profile: dict, wanted: set, general: bool) -> list:
    skills = list(profile.get("skills", []))
    if general:
        return sorted(skills, key=lambda s: (-s.get("evidence_count", 0), s["skill"]))
    return sorted(skills, key=lambda s: (s["skill"] not in wanted,
                                          -s.get("evidence_count", 0)))


def _technical_skills(profile: dict, wanted: set, general: bool) -> list:
    """Compétences techniques : hors soft skills (qui vont en « Atouts »)."""
    return [s for s in _ordered_skills(profile, wanted, general) if not _is_soft(s)]


def _categories(profile: dict, wanted: set, general: bool,
                tech_only: bool = False) -> list:
    """Compétences regroupées par catégorie réelle du profil."""
    groups: dict = {}
    for s in _ordered_skills(profile, wanted, general):
        if tech_only and _is_soft(s):
            continue
        groups.setdefault(s.get("category") or "Autres", []).append(s)
    out = []
    for cat in sorted(groups, key=lambda c: (c == "Autres", c)):
        kws = ", ".join(f"{s['skill']} ({_level(s)})".strip() for s in groups[cat])
        out.append((cat, kws))
    return out


def _soft_skills(profile: dict, wanted: set) -> list:
    out = []
    for s in _ordered_skills(profile, wanted, False):
        cat = (s.get("category") or "").lower()
        if "soft" in cat or "humaine" in cat:
            out.append(f"{s['skill']} ({_level(s)})".strip())
    return out


def _fmt_month(value: str) -> str:
    if value and len(value) >= 7 and value[4] == "-":
        month = int(value[5:7])
        if 1 <= month <= 12:
            return f"{cv_builder.MONTHS_FR[month - 1]} {value[:4]}"
    return value or ""


def _period(e: dict) -> str:
    end = e.get("end_date")
    return " - ".join(filter(None, [_fmt_month(e.get("start_date")),
                                    _fmt_month(end) if end else "présent"]))


def _exp_bullets(e: dict) -> list:
    """Puces réelles : phrases de la description, puis compétences mobilisées."""
    bullets = []
    desc = (e.get("description") or "").strip()
    if desc:
        parts = [p.strip() for p in desc.replace(". ", ".\u0001").split("\u0001") if p.strip()]
        bullets = [p.rstrip(".") + "." for p in parts[:4]]
    if e.get("skills"):
        bullets.append("Compétences mobilisées : " + ", ".join(e["skills"]))
    return bullets


def _years_label(experiences: list) -> Optional[str]:
    """Ancienneté RÉELLE : du premier début au dernier fin (ou aujourd'hui)."""
    starts = [e.get("start_date") for e in experiences if e.get("start_date")]
    ends = [e.get("end_date") for e in experiences if e.get("end_date")]
    if not starts:
        return None
    try:
        first = min(starts)[:7]
        last = (max(ends) if ends else date.today().strftime("%Y-%m"))[:7]
        months = (int(last[:4]) - int(first[:4])) * 12 + int(last[5:7]) - int(first[5:7])
        if months < 12:
            return None
        return f"{months // 12}+"
    except Exception:
        return None


def _kpi_rows(profile: dict) -> list:
    """Chiffres réels du profil, aucune donnée inventée (§47)."""
    rows = []
    exps = profile.get("experiences", [])
    years = _years_label(exps)
    if years:
        rows.append((years, "ans d'expérience"))
    if exps:
        rows.append((str(len(exps)),
                     "expérience" if len(exps) == 1 else "expériences"))
    certs = profile.get("certifications") or []
    if certs:
        rows.append((str(len(certs)),
                     "certification" if len(certs) == 1 else "certifications"))
    return rows[:3]


def _formation_lines(education: list) -> list:
    out = []
    for ed in education or []:
        line = ed.get("degree", "")
        if ed.get("institution"):
            line += f", {ed['institution']}"
        if ed.get("field"):
            line += f" ({ed['field']})"
        years = " - ".join(str(y) for y in [ed.get("start_year"), ed.get("end_year")] if y)
        if years:
            line += f", {years}."
        else:
            line += "."
        out.append(line)
    return out


def _cert_lines(certifications: list) -> list:
    out = []
    for c in certifications or []:
        line = c.get("name", "")
        if c.get("issuer"):
            line += f" - {c['issuer']}"
        if c.get("year"):
            line += f" ({c['year']})"
        out.append(line)
    return out


def _langue_lines(languages: list) -> list:
    return [f"{l['language']} : {l['level']}" if l.get("level") else str(l["language"])
            for l in languages or []]


def _headline(profile: dict, job: Any) -> str:
    return (profile.get("title")
            or (f"Candidature : {job.title}" if job else "Profil professionnel"))


# ------------------------------------------------------------------ mesures

def _nlines(p, txt, w, gap, size, style="") -> int:
    p.set_font(p.fam, style, size)
    return len(p.multi_cell(w, gap, _t(txt), dry_run=True, output="LINES"))


def _mh(p, txt, w, gap, size, style="") -> float:
    return _nlines(p, txt, w, gap, size, style) * gap + 0.6


# ------------------------------------------------------- bandeau d'en-tête

def _band_header(p, theme, user, profile, job, photo, height=50.0,
                 name_size=16, title_size=13.5):
    """Bandeau sombre + filet accent + identité (nom d'abord, comme les
    modèles de référence). Aucun lien inventé : email réel seulement."""
    p.set_fill_color(*theme["band"])
    p.rect(0, 0, 210, height, style="F")
    p.set_fill_color(*theme["bright"])
    p.rect(0, height, 210, 1.6, style="F")
    # Médaillon proportionné au bandeau (33 mm sur le grand, moins sinon).
    ph_size = max(14, min(33, height - 12))
    tx = 12 + ph_size + 4 if photo else 12
    if photo:
        try:
            py = (height - ph_size) / 2
            p.image(photo, x=10, y=py, w=ph_size, h=ph_size)
        except Exception:
            tx = 12
    right = 198

    # Positions proportionnelles à la hauteur du bandeau (50 mm -> le
    # gabarit de référence : 4,5 / 12,5 / 20 / 25,5).
    p.set_xy(tx, height * 0.09)
    p.set_text_color(*WHITE)
    p.set_font(p.fam, "B", name_size)
    p.cell(right - tx, 7, _t(user.full_name).upper())

    titre = _headline(profile, job)
    size = title_size
    p.set_font(p.fam, "B", size)
    while p.get_string_width(_t(titre)) > right - tx - 4 and size > 10:
        size -= 0.5
        p.set_font(p.fam, "B", size)
    p.set_xy(tx, height * 0.25)
    p.set_text_color(*theme["bright"])
    p.cell(right - tx, 5.5, _t(titre))

    contact = [profile.get("location") or "Cameroun"]
    if getattr(user, "email", None):
        contact.append(str(user.email))
    line = "   |   ".join(contact)
    p.set_xy(tx, height * 0.40)
    p.set_text_color(*WHITE)
    p.set_font(p.fam, "", 7.8)
    p.cell(right - tx, 4.5, _t(line[:95]))

    extra = []
    if profile.get("availability"):
        extra.append(f"Disponibilité : {profile['availability']}")
    if getattr(user, "verification_status", None) == "verified":
        extra.append("Profil vérifié OrientSkill AI")
    if extra and height > 34:
        p.set_xy(tx, height * 0.51)
        p.set_text_color(*theme["bright"])
        p.set_font(p.fam, "B", 7.8)
        p.cell(right - tx, 4.5, _t("   -   ".join(extra)[:95]))


# --------------------------------------------------------- barre latérale

def _side_title(p, x, w, y, t, theme):
    p.set_xy(x, y)
    p.set_text_color(*theme["band"])
    p.set_font(p.fam, "B", 9)
    p.cell(w, 5.5, _t(t).upper())
    p.set_fill_color(*theme["bright"])
    p.rect(x, y + 5.8, 16, 1.6, style="F")
    return y + 9.2


def _side_text(p, x, w, y, txt, theme, size=7.8, bold=False, color=None):
    p.set_xy(x, y)
    p.set_text_color(*(color or theme["ink"]))
    p.set_font(p.fam, "B" if bold else "", size)
    p.multi_cell(w, 4.3, _t(txt))
    return p.get_y() + 0.6


def _side_bullet(p, x, w, y, txt, theme, size=7.5):
    p.set_xy(x, y)
    p.set_text_color(*theme["mid"])
    p.set_font(p.fam, "B", size)
    p.cell(3.5, 4.2, "-")
    p.set_xy(x + 3.5, y)
    p.set_text_color(*theme["ink"])
    p.set_font(p.fam, "", size)
    p.multi_cell(w - 3.5, 4.2, _t(txt))
    return p.get_y() + 0.5


def _side_block_h(p, w, b):
    kind, txt, kw = b
    if kind == "text":
        return _mh(p, txt, w, 4.3, kw.get("size", 7.8), "B" if kw.get("bold") else "")
    return _mh(p, txt, w - 3.5, 4.2, kw.get("size", 7.5))


def _side_draw_block(p, x, w, b, y, theme):
    kind, txt, kw = b
    if kind == "text":
        return _side_text(p, x, w, y, txt, theme, **kw)
    return _side_bullet(p, x, w, y, txt, theme, **kw)


def _side_sections(profile, user, wanted) -> list:
    """Sections latérales : uniquement des données réelles du profil."""
    it = lambda t, **kw: ("text", t, kw)
    bl = lambda t, **kw: ("bullet", t, kw)
    sections = []
    contact = []
    if getattr(user, "email", None):
        contact.append(it(str(user.email), color=None))
    contact.append(it(profile.get("location") or "Cameroun"))
    if profile.get("availability"):
        contact.append(it(f"Disponibilité : {profile['availability']}", bold=True))
    if getattr(user, "verification_status", None) == "verified":
        contact.append(it("Profil vérifié OrientSkill AI"))
    if contact:
        sections.append({"title": "Contact", "items": contact})
    skills = _technical_skills(profile, wanted, wanted == set())
    savoir = [bl(f"{s['skill']} ({_level(s)})".strip()) for s in skills[:10]]
    if savoir:
        sections.append({"title": "Savoir faire", "items": savoir})
    certs = [bl(c, size=7.3) for c in _cert_lines(profile.get("certifications", []))]
    if certs:
        sections.append({"title": "Certifications", "items": certs})
    form = [it(f, size=7.3) for f in _formation_lines(profile.get("education", []))]
    if form:
        sections.append({"title": "Formation", "items": form})
    langs = [it(l, size=7.6) for l in _langue_lines(profile.get("languages", []))]
    if langs:
        sections.append({"title": "Langues", "items": langs})
    atouts = [bl(a) for a in _soft_skills(profile, wanted)]
    if atouts:
        sections.append({"title": "Atouts", "items": atouts})
    return sections


def _side_section_h(p, w, sec):
    return 9.2 + sum(_side_block_h(p, w, b) for b in sec["items"])


def _side_fill(p, x, w, sections, y, y_limit, theme):
    """Remplit l'espace : chaque section qui tient est dessinée, les
    autres passent à la page suivante (portage de draw_sidebar)."""
    rest = []
    for sec in sections:
        gap = 0 if not rest and y < 60 else 2
        if y + gap + _side_section_h(p, w, sec) > y_limit:
            rest.append(sec)
            continue
        y += gap
        y = _side_title(p, x, w, y, sec["title"], theme)
        for b in sec["items"]:
            y = _side_draw_block(p, x, w, b, y, theme)
    return y, rest


# ------------------------------------------------- blocs de la colonne main

def _main_title(p, x, w, y, t, theme, full_rule=False):
    p.set_xy(x, y)
    p.set_text_color(*theme["band"])
    p.set_font(p.fam, "B", 11)
    p.cell(w, 6, _t(t).upper())
    yy = y + 6.5
    p.set_fill_color(*theme["bright"])
    if full_rule:
        p.rect(x, yy, w, 0.6, style="F")
    else:
        p.rect(x, yy, 18, 1.8, style="F")
    return y + (7.4 if full_rule else 10.5)


def _par_just(p, x, w, y, txt, theme, size=8.4, gap=4.5, color=None):
    p.set_xy(x, y)
    p.set_text_color(*(color or theme["ink"]))
    p.set_font(p.fam, "", size)
    p.multi_cell(w, gap, _t(txt), align="J")
    return p.get_y() + 1.4


def _kpi_row(p, x, y, rows, theme, box_w=41.5, box_h=13):
    bx = x
    for num, lab in rows:
        p.set_fill_color(*_mix(theme["bright"], WHITE, 0.88))
        p.rect(bx, y, box_w, box_h, style="F")
        p.set_draw_color(*_mix(theme["mid"], WHITE, 0.45))
        p.set_line_width(0.25)
        p.rect(bx, y, box_w, box_h, style="D")
        p.set_line_width(0.2)
        p.set_xy(bx, y + 1)
        p.set_text_color(*theme["band"])
        p.set_font(p.fam, "B", 11)
        p.cell(box_w, 5, _t(num), align="C")
        p.set_xy(bx, y + 6.8)
        p.set_font(p.fam, "", 7)
        p.set_text_color(*GRAY)
        p.cell(box_w, 4, _t(lab), align="C")
        bx += box_w + 2.5
    return y + box_h + 3


def _job_h(p, w, poste, ent, per, bullets):
    total = 9.8
    for b in bullets:
        total += _nlines(p, b, w - 4, 4.3, 8) * 4.3 + 0.5
    return total + 2.4


def _job(p, x, w, y, e, theme, badge=True):
    poste = e.get("title", "")
    ent = e.get("organization", "")
    per = _period(e)
    bullets = _exp_bullets(e)
    p.set_xy(x, y)
    p.set_font(p.fam, "B", 9)
    p.set_text_color(*theme["band"])
    p.cell(w - 46, 5, _t(poste))
    if badge and per:
        p.set_fill_color(*theme["band"])
        p.set_text_color(*WHITE)
        p.set_font(p.fam, "B", 6.8)
        p.cell(46, 5, " " + _t(per), fill=True)
    else:
        p.cell(46, 5, "")
    y = p.get_y() + 5
    if ent or per:
        p.set_xy(x, y)
        p.set_font(p.fam, "B", 8)
        p.set_text_color(*theme["mid"])
        p.write(4.4, _t(ent))
        label = cv_builder.TYPE_LABELS.get(e.get("type", "formal"), "")
        if label:
            p.set_text_color(*GRAY)
            p.set_font(p.fam, "I", 7.6)
            p.write(4.4, "   " + _t(label))
        y = p.get_y() + 4.8
    for b in bullets:
        p.set_xy(x, y)
        p.set_text_color(*theme["mid"])
        p.set_font(p.fam, "B", 8)
        p.cell(4, 4.3, "-")
        p.set_xy(x + 4, y)
        p.set_text_color(*theme["ink"])
        p.set_font(p.fam, "", 8)
        p.multi_cell(w - 4, 4.3, _t(b), align="J")
        y = p.get_y() + 0.5
    return y + 2.4


def _skill_box_h(p, w, label, kws):
    return 5.9 + _nlines(p, kws, w - 3, 3.8, 7.4) * 3.8 + 1.2


def _skill_box(p, x, w, y, label, kws, theme):
    p.set_xy(x + 1.5, y + 1)
    p.set_font(p.fam, "B", 7.4)
    p.set_text_color(*theme["mid"])
    p.cell(w - 3, 3.8, _t(label))
    p.set_xy(x + 1.5, y + 4.9)
    p.set_font(p.fam, "", 7.4)
    p.set_text_color(*theme["ink"])
    p.multi_cell(w - 3, 3.8, _t(kws), align="J")
    y1 = p.get_y() + 1
    p.set_draw_color(*theme["line"])
    p.set_line_width(0.25)
    p.rect(x, y, w, y1 - y, style="D")
    p.set_line_width(0.2)
    return y1 + 1.2


def _projet_h(p, w, desc):
    return 4.4 + _nlines(p, desc, w - 4, 4.3, 8) * 4.3 + 1.8


def _projet(p, x, w, y, pr, theme):
    p.set_xy(x, y)
    p.set_text_color(*theme["mid"])
    p.set_font(p.fam, "B", 8.4)
    p.cell(4, 4.4, "-")
    p.set_xy(x + 4, y)
    p.set_text_color(*theme["band"])
    p.set_font(p.fam, "B", 8.4)
    p.write(4.4, _t(pr.get("name", "")))
    y = p.get_y() + 4.4
    desc = pr.get("description") or ""
    if desc:
        p.set_xy(x + 4, y)
        p.set_text_color(*theme["ink"])
        p.set_font(p.fam, "", 8)
        p.multi_cell(w - 4, 4.3, _t(desc), align="J")
        y = p.get_y()
    if pr.get("skills"):
        p.set_xy(x + 4, y)
        p.set_text_color(*GRAY)
        p.set_font(p.fam, "I", 7.4)
        p.multi_cell(w - 4, 4, _t("Compétences : " + ", ".join(pr["skills"])), align="J")
        y = p.get_y()
    return y + 1.8


def _formation_entry(p, x, w, y, line, theme):
    p.set_xy(x, y)
    p.set_text_color(*theme["mid"])
    p.set_font(p.fam, "B", 8)
    p.cell(4, 4.3, "-")
    p.set_xy(x + 4, y)
    p.set_text_color(*theme["ink"])
    p.set_font(p.fam, "", 8)
    p.multi_cell(w - 4, 4.3, _t(line), align="J")
    return p.get_y() + 0.8


# ------------------------------------------------------- CV « deux colonnes »

LX, LW = 8, 58
RX, RW = 71, 131
TOP = 55
SB_W = 68
BOTTOM = 284
SB_BOTTOM = 290


def _build_two_col(profile, job, user, match, theme) -> bytes:
    wanted = (set(match["covered"]) | set(match["partial"])) if match else set()
    general = match is None
    photo = _medaillon(user, theme["bright"], theme["band"])

    p = FPDF("P", "mm", "A4")
    _setup_fonts(p)
    p.set_auto_page_break(False)
    p.set_margins(10, 10, 10)
    p.set_title(f"CV - {user.full_name} - {job.title if job else 'profil complet'}")
    p.set_author(user.full_name)
    p.add_page()

    _band_header(p, theme, user, profile, job, photo, height=50)

    # fond de barre latérale page 1
    p.set_fill_color(*theme["soft"])
    p.rect(0, 51.6, SB_W, 245.4, style="F")
    p.set_fill_color(*theme["bright"])
    p.rect(SB_W, 51.6, 1.4, 245.4, style="F")

    sections = _side_sections(profile, user, wanted)
    state = {"rest": sections, "y": TOP}

    def draw_side(y):
        return _side_fill(p, LX, LW, state["rest"], y, SB_BOTTOM, theme)

    def new_page():
        p.add_page()
        p.set_fill_color(*theme["soft"])
        p.rect(0, 0, SB_W, 297, style="F")
        p.set_fill_color(*theme["bright"])
        p.rect(SB_W, 0, 1.4, 297, style="F")
        state["y"], state["rest"] = _side_fill(p, LX, LW, state["rest"], 10, SB_BOTTOM, theme)
        return 10

    def guard(y, need):
        return new_page() if y + need > BOTTOM else y

    state["y"], state["rest"] = draw_side(TOP)

    # ----- colonne principale
    y = TOP
    summary = profile.get("summary")
    if not summary and match and match["covered"] and job is not None:
        summary = (f"Profil orienté « {job.title} » ; compétences pertinentes "
                   f"déjà acquises : {', '.join(match['covered'][:5])}.")
    if summary:
        y = _main_title(p, RX, RW, y, "Profil", theme)
        y = _par_just(p, RX, RW, y, summary, theme)
    kpis = _kpi_rows(profile)
    if kpis:
        y = _kpi_row(p, RX, y, kpis, theme)

    experiences = sorted(
        profile.get("experiences", []),
        key=(lambda e: len(set(e.get("skills") or []) & wanted)) if match
        else (lambda e: (e.get("end_date") or "9999-12", e.get("start_date") or "")),
        reverse=True,
    )
    if experiences:
        first = experiences[0]
        y = guard(y, 10.5 + _job_h(p, RW, first.get("title", ""),
                                   first.get("organization", ""), "", _exp_bullets(first)))
        y = _main_title(p, RX, RW, y, "Expérience professionnelle", theme)
        for e in experiences:
            y = guard(y, _job_h(p, RW, e.get("title", ""), e.get("organization", ""),
                                 "", _exp_bullets(e)))
            y = _job(p, RX, RW, y, e, theme)

    cats = _categories(profile, wanted, general, tech_only=True)
    if cats:
        first = cats[0]
        y = guard(y, 10.5 + _skill_box_h(p, RW, first[0], first[1]))
        y = _main_title(p, RX, RW, y,
                        "Compétences techniques" if cats[0][0] != "Autres" else "Compétences",
                        theme)
        for label, kws in cats:
            y = guard(y, _skill_box_h(p, RW, label, kws))
            y = _skill_box(p, RX, RW, y, label, kws, theme)

    projects = profile.get("projects", [])
    if projects:
        y = guard(y, 10.5 + _projet_h(p, RW, projects[0].get("description") or ""))
        y = _main_title(p, RX, RW, y, "Projets", theme)
        for pr in projects:
            y = guard(y, _projet_h(p, RW, pr.get("description") or ""))
            y = _projet(p, RX, RW, y, pr, theme)

    while state["rest"]:
        state["y"], state["rest"] = _side_fill(
            p, LX, LW, state["rest"], state["y"], SB_BOTTOM, theme)
        if state["rest"]:
            new_page()

    return bytes(p.output())


# ------------------------------------------------- CV une colonne (variantes)

def _build_single(profile, job, user, match, theme, template) -> bytes:
    wanted = (set(match["covered"]) | set(match["partial"])) if match else set()
    general = match is None
    variant = {
        "moderne": dict(ml=15, band=30, photo_band=True, kpi=True, boxes=True,
                        badged=True, name=15, title=12.5, guard_y=279),
        "classique": dict(ml=18, band=0, photo_band=False, kpi=True, boxes=False,
                          badged=True, name=18, title=13, guard_y=279),
        "ats": dict(ml=18, band=0, photo_band=False, kpi=False, boxes=False,
                    badged=False, name=19, title=15, guard_y=279),
        "elegant": dict(ml=20, band=0, photo_band=False, kpi=False, boxes=False,
                        badged=False, name=20, title=13, guard_y=279),
        "compact": dict(ml=11, band=24, photo_band=True, kpi=True, boxes=True,
                        badged=True, name=13.5, title=11, guard_y=282),
    }[template]
    serif = template == "elegant"

    photo = None
    if variant["photo_band"] or template in ("classique", "ats"):
        ring = theme["bright"]
        bg = theme["band"] if variant["photo_band"] else WHITE
        photo = _medaillon(user, ring, bg)

    p = FPDF("P", "mm", "A4")
    _setup_fonts(p, serif=serif)
    p.set_auto_page_break(True, margin=12)
    ml = variant["ml"]
    p.set_margins(ml, 12, 15)
    cw = 210 - ml - 15
    p.set_title(f"CV - {user.full_name} - {job.title if job else 'profil complet'}")
    p.set_author(user.full_name)
    p.add_page()

    # ---------- en-tête
    if variant["band"]:
        _band_header(p, theme, user, profile, job, photo,
                     height=variant["band"], name_size=variant["name"],
                     title_size=variant["title"])
        y = variant["band"] + 8
    else:
        photo_x = 162 if photo else None
        if photo:
            try:
                p.image(photo, x=162, y=8, w=30, h=30)
            except Exception:
                photo_x = None
        maxw = 150 if photo else cw
        p.set_xy(ml, 8.5)
        p.set_text_color(*theme["band"])
        p.set_font(p.fam, "B", variant["name"])
        p.cell(maxw, 8, _t(user.full_name).upper())
        titre = _headline(profile, job)
        size = variant["title"]
        p.set_font(p.fam, "B", size)
        while p.get_string_width(_t(titre)) > maxw and size > 10:
            size -= 0.5
            p.set_font(p.fam, "B", size)
        base_y = 8.5 + variant["name"] * 0.5
        p.set_xy(ml, base_y)
        p.set_text_color(*theme["mid"])
        p.cell(maxw, 6.5, _t(titre))
        domains = cv_builder.domain_line(profile) if template == "ats" else ""
        shift = 4.8 if domains else 0
        if domains:
            p.set_xy(ml, base_y + 7.4)
            p.set_text_color(*theme["mid"])
            p.set_font(p.fam, "I", 8)
            p.cell(maxw, 4.5, _t("Domaines : " + domains))
        contact = [profile.get("location") or "Cameroun"]
        if getattr(user, "email", None):
            contact.append(str(user.email))
        p.set_xy(ml, base_y + 8 + shift)
        p.set_text_color(*theme["ink"])
        p.set_font(p.fam, "", 8.6)
        p.cell(maxw, 5, _t("   |   ".join(contact)))
        extra = []
        if profile.get("availability"):
            extra.append(f"Disponibilité : {profile['availability']}")
        if getattr(user, "verification_status", None) == "verified":
            extra.append("Profil vérifié OrientSkill AI")
        if extra:
            p.set_xy(ml, base_y + 13.5 + shift)
            p.set_text_color(*GRAY)
            p.set_font(p.fam, "", 7.8)
            p.cell(maxw, 4.5, _t("   |   ".join(extra)))
        y = base_y + 19 + shift
        p.set_draw_color(*_mix(theme["bright"], WHITE, 0.35))
        p.set_line_width(0.8)
        p.line(ml, y, 210 - 15, y)
        p.set_line_width(0.2)
        y += 4

    def sec(t, full=False):
        nonlocal y
        p.set_xy(ml, y)
        y = _main_title(p, ml, cw, y, t, theme, full_rule=full)

    def par(txt, size=9, gap=4.6, color=None):
        nonlocal y
        p.set_xy(ml, y)
        p.set_text_color(*(color or theme["ink"]))
        p.set_font(p.fam, "", size)
        p.multi_cell(cw, gap, _t(txt), align="J")
        y = p.get_y() + 1.2

    def bullet(txt, size=9):
        nonlocal y
        if y > variant["guard_y"]:
            p.add_page()
            y = 12
        p.set_xy(ml, y)
        p.set_text_color(*theme["mid"])
        p.set_font(p.fam, "B", size)
        p.cell(4.5, 4.4, "-")
        p.set_xy(ml + 4.5, y)
        p.set_text_color(*theme["ink"])
        p.set_font(p.fam, "", size)
        p.multi_cell(cw - 4.5, 4.4, _t(txt), align="J")
        y = p.get_y() + 0.7

    # ---------- Profil
    summary = profile.get("summary")
    if not summary and match and match["covered"] and job is not None:
        summary = (f"Profil orienté « {job.title} » ; compétences pertinentes "
                   f"déjà acquises : {', '.join(match['covered'][:5])}.")
    if summary:
        sec("Profil", full=serif)
        par(summary)

    kpis = _kpi_rows(profile)
    if kpis and variant["kpi"]:
        y = _kpi_row(p, ml, y, kpis, theme)

    # ---------- Compétences (avant l'expérience, comme le gabarit ATS)
    cats = _categories(profile, wanted, general)
    if cats:
        if template == "ats":
            skills_title = "Compétences"
        else:
            skills_title = (f"Compétences (poste visé : {job.title})"
                            if job else "Compétences")
        sec(skills_title, full=serif)
        for label, kws in cats:
            if variant["boxes"]:
                if y > variant["guard_y"] - 14:
                    p.add_page()
                    y = 12
                y = _skill_box(p, ml, cw, y, label, kws, theme)
            else:
                par(f"**{label}** : {kws}", size=9 if not serif else 9.6,
                    gap=4.6 if not serif else 5)

    # ---------- Expérience
    experiences = sorted(
        profile.get("experiences", []),
        key=(lambda e: len(set(e.get("skills") or []) & wanted)) if match
        else (lambda e: (e.get("end_date") or "9999-12", e.get("start_date") or "")),
        reverse=True,
    )
    if experiences:
        sec("Expérience professionnelle", full=serif)
        for e in experiences:
            if y > variant["guard_y"] - 10:
                p.add_page()
                y = 12
            y = _job(p, ml, cw, y, e, theme, badge=variant["badged"])

    # ---------- Projets
    projects = profile.get("projects", [])
    if projects:
        sec("Projets", full=serif)
        for pr in projects:
            desc = pr.get("description") or ""
            line = f"**{pr.get('name', '')}** : {desc}" if desc else pr.get("name", "")
            if pr.get("skills"):
                line += " Compétences : " + ", ".join(pr["skills"])
            p.set_xy(ml, y)
            p.set_text_color(*theme["mid"])
            p.set_font(p.fam, "B", 9)
            p.cell(4.5, 4.4, "-")
            p.set_xy(ml + 4.5, y)
            p.set_text_color(*theme["ink"])
            p.set_font(p.fam, "", 9)
            p.multi_cell(cw - 4.5, 4.4, _t(line), align="J", markdown=True)
            y = p.get_y() + 1.2

    # ---------- Certifications / Formation / Langues
    certs = _cert_lines(profile.get("certifications", []))
    if certs:
        sec("Certifications", full=serif)
        for line in certs:
            bullet(line)
    form = _formation_lines(profile.get("education", []))
    if form:
        sec("Formation", full=serif)
        for line in form:
            p.set_xy(ml, y)
            p.set_text_color(*theme["mid"])
            p.set_font(p.fam, "B", 9)
            p.cell(4.5, 4.4, "-")
            p.set_xy(ml + 4.5, y)
            p.set_text_color(*theme["ink"])
            p.set_font(p.fam, "", 9)
            p.multi_cell(cw - 4.5, 4.4, _t(line), align="J")
            y = p.get_y() + 0.8
    langs = _langue_lines(profile.get("languages", []))
    if langs:
        sec("Langues", full=serif)
        par("  |  ".join(langs))

    return bytes(p.output())


# ----------------------------------------------------------------- lettres

L_ML = 18
L_XD = 118
L_WD = 210 - 15 - L_XD
L_LARG = 210 - L_ML - 15
L_WO = int(210 / 2) - L_ML


def _letter_common(p, theme, user, profile):
    p.set_fill_color(*theme["band"])
    p.rect(0, 0, 210, 26, style="F")
    p.set_fill_color(*theme["bright"])
    p.rect(0, 26, 210, 1.2, style="F")
    p.set_xy(L_ML, 4.5)
    p.set_text_color(*WHITE)
    p.set_font(p.fam, "B", 11.5)
    p.cell(L_LARG, 5, _t(user.full_name).upper())
    p.set_xy(L_ML, 10.8)
    p.set_text_color(*theme["bright"])
    p.set_font(p.fam, "B", 10)
    p.cell(L_LARG, 4.6, _t(profile.get("title") or ""))
    p.set_xy(L_ML, 17.2)
    p.set_font(p.fam, "", 7.8)
    p.set_text_color(*SOFTTXT)
    contact = [profile.get("location") or "Cameroun"]
    if getattr(user, "email", None):
        contact.append(str(user.email))
    p.cell(L_LARG, 4.5, _t("  |  ".join(contact)))


def _build_letter(profile, job, user, structure, theme, template) -> bytes:
    p = FPDF("P", "mm", "A4")
    _setup_fonts(p, serif=False)
    p.set_auto_page_break(True, margin=15)
    p.set_margins(L_ML, 15, 15)
    label = f" - {job.title}" if job is not None else " (généraliste)"
    p.set_title(f"Lettre de motivation - {user.full_name}{label}")
    p.set_author(user.full_name)
    p.add_page()

    today = date.today()
    date_words = f"{profile.get('location') or 'Cameroun'}, le {today.day} {MOIS[today.month - 1]} {today.year}"

    # Ciblée par une offre, ou généraliste : le destinataire reste alors à
    # compléter par le candidat (jamais de coordonnées inventées, §47).
    company = job.company if job is not None else "[Nom de l'entreprise]"
    city = job.location if job is not None else "[Ville]"
    objet = ("candidature au poste de « " + job.title + " »" if job is not None
             else "candidature spontanée")

    if template == "email":
        p.set_xy(L_ML, 15)
        p.set_text_color(*theme["band"])
        p.set_font(p.fam, "B", 10.5)
        p.multi_cell(L_LARG, 5.5, _t(f"Objet : {objet} - {company}"), align="L")
        y = p.get_y() + 1.5
        p.set_draw_color(*theme["bright"])
        p.set_line_width(0.5)
        p.line(L_ML, y, L_ML + 42, y)
        p.set_line_width(0.2)
        y += 7
    else:
        _letter_common(p, theme, user, profile)
        y = 33
        p.set_xy(L_XD, y)
        p.set_text_color(*theme["band"])
        p.set_font(p.fam, "B", 9.5)
        p.cell(L_WD, 4.8, _t(company))
        y += 4.8
        p.set_xy(L_XD, y)
        p.set_font(p.fam, "", 9)
        p.set_text_color(*theme["ink"])
        if city:
            p.cell(L_WD, 4.6, _t(city))
            y += 4.6
        y += 6
        p.set_xy(L_XD, y)
        p.set_font(p.fam, "", 9.5)
        p.cell(L_WD, 4.8, _t(date_words))
        y += 9
        p.set_xy(L_ML, y)
        p.set_text_color(*theme["band"])
        p.set_font(p.fam, "B", 10.5)
        p.multi_cell(L_WO, 5.5, _t(f"Objet : {objet}"),
                     align="L")
        y = p.get_y() + 1.5
        if template == "moderne":
            p.set_fill_color(*_mix(theme["bright"], WHITE, 0.88))
            p.rect(L_ML, y, min(L_LARG, 90), 2.4, style="F")
        else:
            p.set_draw_color(*theme["bright"])
            p.set_line_width(0.5)
            p.line(L_ML, y, L_ML + 42, y)
            p.set_line_width(0.2)
        y += 7

    p.set_xy(L_ML, y)
    p.set_text_color(*theme["ink"])
    p.set_font(p.fam, "B", 10)
    p.cell(L_LARG, 5.5, _t(structure["salutation"]))
    y += 9

    p.set_font(p.fam, "", 10)
    p.set_text_color(*theme["ink"])
    for para in structure["paragraphs"] + list(structure["closing"]):
        p.set_xy(L_ML, y)
        p.multi_cell(L_LARG, 5.5, _t(para), align="J")
        y = p.get_y() + 3.5

    y += 10
    p.set_xy(L_XD, y)
    p.set_text_color(*theme["band"])
    p.set_font(p.fam, "B", 10.5)
    p.cell(L_WD, 5.5, _t(structure["signature"]))
    if template != "email":
        y += 24
        p.set_xy(L_ML, min(y, 272))
        p.set_text_color(*GRAY)
        p.set_font(p.fam, "I", 8)
        p.cell(L_LARG, 4, _t("PJ : CV " + ("ciblé" if job is not None else "généraliste")
                             + " OrientSkill AI"))
    return bytes(p.output())


# ----------------------------------------------------------------- API

def build_cv_pdf(
    profile: dict[str, Any],
    job: Optional[Any],
    user: Any,
    taxonomy: Optional[SkillsTaxonomy] = None,
    template: str = "classique",
    accent: Optional[str] = None,
) -> bytes:
    """CV A4, modèle et accent au choix (§16, §47).

    ``job=None`` produit le CV GÉNÉRALISTE (profil complet, sans ciblage).
    """
    match = None
    if job is not None:
        match = compute_match(profile.get("skills", []), job.required_skills, taxonomy)
    theme = _theme(template, accent)
    if template == "deux_colonnes":
        return _build_two_col(profile, job, user, match, theme)
    return _build_single(profile, job, user, match, theme, template)


def build_letter_pdf(
    profile: dict[str, Any],
    job: Optional[Any],
    user: Any,
    taxonomy: Optional[SkillsTaxonomy] = None,
    template: str = "classique",
    accent: Optional[str] = None,
) -> bytes:
    """Lettre de motivation A4 (§17) : classique, moderne ou courriel.

    ``job=None`` produit la LETTRE GÉNÉRALISTE : destinataire à compléter
    ([Nom de l'entreprise], [Ville]), contenu = profil validé uniquement.
    """
    structure = cv_builder.build_letter_paragraphs(profile, job, user, taxonomy)
    theme = _theme(template, accent)
    return _build_letter(profile, job, user, structure, theme, template)
