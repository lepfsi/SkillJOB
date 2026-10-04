"""Rendu PDF A4 professionnel des documents de candidature.

Trois modèles de CV :
- ``classique`` : en-tête vert institutionnel, compétences ciblées en
  deux colonnes, expériences avec dates à droite ;
- ``ats``       : noir et blanc, une colonne, intitulés standards,
  aucune règle décorative — lisible par les logiciels de tri ;
- ``moderne``   : nom en couleur d'accent, résumé mis en avant.

Conventions : CV aux normes internationales (EN/FR), lettre aux
conventions épistolaires françaises. Contenu exclusivement issu du
profil validé (§47 : pas d'invention).
"""
import os
from io import BytesIO
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app import config
from app.services import cv_builder
from app.services.matching import compute_match
from app.services.skills_taxonomy import SkillsTaxonomy

PAGE_W, PAGE_H = A4
MARGIN = 1.7 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

_GREEN = colors.HexColor("#0A4530")
_ACCENT = colors.HexColor("#E67E22")

# ----------------------------------------------------------------- styles

_BASE = dict(
    ink="#1A211D",
    primary="#0A4530",
    line="#C9D3CD",
)


def _styles(template: str) -> dict:
    """Palette et niveaux selon le modèle de CV."""
    ats = template == "ats"
    moderne = template == "moderne"
    if ats:
        primary = ink = "#000000"
        line = "#999999"
    elif moderne:
        primary = "#E67E22"
        ink = "#1A211D"
        line = "#E0C4A8"
    else:
        primary = _BASE["primary"]
        ink = _BASE["ink"]
        line = _BASE["line"]

    s = {
        "name": ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=16.5,
                               leading=19, textColor=colors.HexColor(primary), spaceAfter=1),
        "headline": ParagraphStyle("headline", fontName="Helvetica", fontSize=10.5,
                                   leading=13, textColor=colors.HexColor(ink)),
        "contact": ParagraphStyle("contact", fontName="Helvetica", fontSize=8.5,
                                  leading=11, textColor=colors.HexColor("#55645C")),
        "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=10.5,
                                   leading=13, textColor=colors.HexColor(primary),
                                   spaceBefore=10, spaceAfter=3),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.5,
                               leading=13.5, textColor=colors.HexColor(ink)),
        "bodySmall": ParagraphStyle("bodySmall", fontName="Helvetica", fontSize=8.8,
                                    leading=12, textColor=colors.HexColor(ink)),
        "entryTitle": ParagraphStyle("entryTitle", fontName="Helvetica-Bold",
                                     fontSize=10, leading=12.5, textColor=colors.HexColor(ink)),
        "entrySub": ParagraphStyle("entrySub", fontName="Helvetica-Oblique",
                                   fontSize=8.8, leading=11, textColor=colors.HexColor("#55645C")),
        "date": ParagraphStyle("date", fontName="Helvetica", fontSize=8.8,
                               leading=11, textColor=colors.HexColor("#55645C"), alignment=2),
        "ats": ats,
    }
    if moderne:
        s["name"].fontSize = 18
        s["headline"].fontSize = 11
    s["primary"] = primary
    s["ink"] = ink
    s["line"] = line
    return s


def _esc(text: Any) -> str:
    # Entités XML construites via unicode (évite tout caractère littéral ambigu).
    amp = "\u0026amp;"
    lt = "\u0026lt;"
    gt = "\u0026gt;"
    return str(text or "").replace("\u0026", amp).replace("<", lt).replace(">", gt)


def _section(title: str, s: dict) -> list:
    out = [Paragraph(_esc(title).upper(), s["section"])]
    if not s["ats"]:
        out.append(HRFlowable(width="100%", thickness=0.7,
                              color=colors.HexColor(s["line"]), spaceAfter=5))
    else:
        out.append(Spacer(1, 3))
    return out


def _photo_flowable(user: Any, height_pt: float = 80) -> Any:
    """Photo de profil (optionnelle) pour l'en-tête du CV."""
    path = getattr(user, "photo_path", None)
    if not path:
        return None
    full = config.BASE_DIR / path
    if not full.exists() or not os.access(full, os.R_OK):
        return None
    try:
        from PIL import Image as PILImage
        with PILImage.open(full) as img:
            w, h = img.size
        ratio = w / h
        return Image(str(full), height=height_pt, width=height_pt * ratio)
    except Exception:
        return None


def _header(user: Any, profile: dict, s: dict) -> list:
    """En-tête CV : identité, titre, contact (+ photo si présente)."""
    headline = Paragraph(_esc(profile.get("title") or ""), s["headline"])
    contact_bits = [profile.get("location") or "Cameroun"]
    if getattr(user, "email", None):
        contact_bits.append(str(user.email))
    if profile.get("availability"):
        contact_bits.append(f"Disponibilité : {profile['availability']}")
    if getattr(user, "verification_status", None) == "verified":
        contact_bits.append("Profil vérifié OrientSkill AI")
    contact = Paragraph(_esc("  ·  ".join(contact_bits)), s["contact"])

    photo = _photo_flowable(user)
    if photo is None:
        return [
            Paragraph(_esc(user.full_name), s["name"]),
            headline,
            contact,
            Spacer(1, 6),
        ]
    left_cell = [
        Paragraph(_esc(user.full_name), s["name"]),
        headline,
        contact,
    ]
    table = Table([[left_cell, photo]], colWidths=[CONTENT_W - 90, 90])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [table, Spacer(1, 6)]


def _skills_block(skills: list, wanted: set, s: dict) -> list:
    ordered = sorted(
        skills,
        key=lambda x: (x["skill"] not in wanted, -x.get("evidence_count", 0)),
    )
    rows = []
    for sk in ordered:
        prof = cv_builder.PROFICIENCY_LABELS.get(sk.get("proficiency", ""), "")
        rows.append([Paragraph(_esc(sk["skill"]), s["bodySmall"]),
                     Paragraph(_esc(prof), s["date"])])
    if s["ats"]:
        # Mono-colonne ATS : toutes les compétences en un bloc continu
        text = " · ".join(
            f"{sk['skill']} ({cv_builder.PROFICIENCY_LABELS.get(sk.get('proficiency', ''), '')})"
            for sk in ordered
        )
        return [Paragraph(_esc(text), s["bodySmall"])]
    # Classique / moderne : deux colonnes de paires
    half = (len(rows) + 1) // 2
    left, right = rows[:half], rows[half:]
    cells = []
    for i in range(half):
        l = left[i] if i < len(left) else ["", ""]
        r = right[i] if i < len(right) else ["", ""]
        cells.append([l[0], l[1], r[0], r[1]])
    table = Table(
        cells,
        colWidths=[CONTENT_W * 0.36, CONTENT_W * 0.14, CONTENT_W * 0.36, CONTENT_W * 0.14],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    return [table]


def _experience_row(e: dict, s: dict, wanted: set) -> list:
    period = " – ".join(filter(None, [e.get("start_date"), e.get("end_date") or "présent"]))
    label = cv_builder.TYPE_LABELS.get(e.get("type", "formal"), "Expérience")
    if s["ats"]:
        flow = [Paragraph(_esc(f"{e.get('title', '')} · {e.get('organization', '')}".rstrip(" ·")),
                          s["entryTitle"])]
        flow.append(Paragraph(_esc(f"{label} · {period}"), s["date"]))
        if e.get("description"):
            flow.append(Paragraph(_esc(e["description"]), s["bodySmall"]))
        if e.get("skills"):
            flow.append(Paragraph("Compétences mobilisées : " + _esc(", ".join(e["skills"])),
                                  s["bodySmall"]))
        return flow
    left = [Paragraph(_esc(e.get("title", "")), s["entryTitle"])]
    org = e.get("organization")
    if org:
        left.append(Paragraph(_esc(org), s["entrySub"]))
    if e.get("description"):
        left.append(Paragraph(_esc(e["description"]), s["bodySmall"]))
    if e.get("skills"):
        left.append(Paragraph("Compétences mobilisées : " + _esc(", ".join(e["skills"])),
                              s["bodySmall"]))
    right = [Paragraph(_esc(period), s["date"]), Paragraph(_esc(label), s["entrySub"])]
    table = Table([[left, right]], colWidths=[CONTENT_W * 0.72, CONTENT_W * 0.28])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return [table]


def _two_col_row(left_flow, right_flow, s: dict) -> list:
    """Une rangée « contenu | dates » ; en ATS, contenu pleine largeur."""
    if s["ats"]:
        return [left_flow]
    table = Table([[left_flow, right_flow]], colWidths=[CONTENT_W * 0.72, CONTENT_W * 0.28])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return [table]


def build_cv_pdf(
    profile: dict[str, Any],
    job: Any,
    user: Any,
    taxonomy: Optional[SkillsTaxonomy] = None,
    template: str = "classique",
) -> bytes:
    """CV ciblé A4, modèle au choix (classique / ats / moderne)."""
    s = _styles(template)
    match = compute_match(profile.get("skills", []), job.required_skills, taxonomy)
    wanted = set(match["covered"]) | set(match["partial"])

    story: list = []
    story += _header(user, profile, s)
    story.append(HRFlowable(width="100%", thickness=1.1 if not s["ats"] else 0.7,
                            color=colors.HexColor(s["primary"] if not s["ats"] else "#000000"),
                            spaceAfter=2))

    # Résumé
    summary = profile.get("summary")
    if not summary and match["covered"]:
        summary = (
            f"Profil orienté « {job.title} » ; compétences pertinentes déjà "
            f"acquises : {', '.join(match['covered'][:5])}."
        )
    if summary:
        story += _section("Résumé", s)
        story.append(Paragraph(_esc(summary), s["body"]))

    # Compétences
    skills = profile.get("skills", [])
    if skills:
        story += _section(f"Compétences (poste visé : {job.title})", s)
        story += _skills_block(skills, wanted, s)

    # Expériences
    experiences = sorted(
        profile.get("experiences", []),
        key=lambda e: len(set(e.get("skills") or []) & wanted),
        reverse=True,
    )
    if experiences:
        story += _section("Expérience professionnelle", s)
        for e in experiences:
            story += _experience_row(e, s, wanted)
            story.append(Spacer(1, 6))

    # Projets
    if profile.get("projects"):
        story += _section("Projets", s)
        for p in profile["projects"]:
            line = p.get("name", "")
            if p.get("description"):
                line += f" : {p['description']}"
            story.append(Paragraph("· " + _esc(line), s["bodySmall"]))
            story.append(Spacer(1, 2))

    # Formation
    if profile.get("education"):
        story += _section("Formation", s)
        for ed in profile["education"]:
            period = " – ".join(str(y) for y in [ed.get("start_year"), ed.get("end_year")] if y)
            left = Paragraph(
                _esc(ed.get("degree", ""))
                + (f", {_esc(ed['institution'])}" if ed.get("institution") else "")
                + (f" ({_esc(ed['field'])})" if ed.get("field") else ""),
                s["bodySmall"])
            story += _two_col_row(left, Paragraph(_esc(period), s["date"]), s)
            story.append(Spacer(1, 2))

    # Certifications
    if profile.get("certifications"):
        story += _section("Certifications", s)
        for c in profile["certifications"]:
            entry = c.get("name", "")
            if c.get("issuer"):
                entry += f" · {c['issuer']}"
            if c.get("year"):
                entry += f" ({c['year']})"
            story.append(Paragraph("· " + _esc(entry), s["bodySmall"]))
            story.append(Spacer(1, 2))

    # Langues
    if profile.get("languages"):
        story += _section("Langues", s)
        text = ", ".join(
            f"{l['language']} ({l['level']})" if l.get("level") else str(l["language"])
            for l in profile["languages"]
        )
        story.append(Paragraph(_esc(text), s["bodySmall"]))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=1.5 * cm, bottomMargin=1.4 * cm,
        title=f"CV — {user.full_name} — {job.title}",
        author=user.full_name,
    )
    doc.build(story)
    return buffer.getvalue()


def build_letter_pdf(
    profile: dict[str, Any],
    job: Any,
    user: Any,
    taxonomy: Optional[SkillsTaxonomy] = None,
) -> bytes:
    """Lettre de motivation A4, conventions épistolaires françaises."""
    structure = cv_builder.build_letter_paragraphs(profile, job, user, taxonomy)
    s = _styles("classique")

    story: list = []
    sender_lines = [str(user.full_name), profile.get("title") or ""]
    if profile.get("location"):
        sender_lines.append(str(profile["location"]))
    if getattr(user, "email", None):
        sender_lines.append(str(user.email))
    sender = "<br/>".join(_esc(x) for x in sender_lines if x)
    recipient = "<br/>".join(_esc(x) for x in [job.company, job.location] if x)

    head = Table(
        [[Paragraph(sender, s["body"]), Paragraph(recipient, s["date"])]],
        colWidths=[CONTENT_W * 0.6, CONTENT_W * 0.4],
    )
    head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(head)
    story.append(Paragraph(_esc(f"Écrit le {structure['date_text']}"), s["contact"]))
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(f"<b>Objet :</b> candidature au poste de « {_esc(job.title)} »",
                  ParagraphStyle("objet", parent=s["body"], fontSize=10.5)))
    story.append(Spacer(1, 8))

    story.append(Paragraph(_esc(structure["salutation"]), s["body"]))
    story.append(Spacer(1, 8))
    for para in structure["paragraphs"]:
        story.append(Paragraph(_esc(para), s["body"]))
        story.append(Spacer(1, 8))
    for closing in structure["closing"]:
        story.append(Paragraph(_esc(closing), s["body"]))
        story.append(Spacer(1, 8))
    story.append(Spacer(1, 14))
    story.append(Paragraph(_esc(structure["signature"]),
                           ParagraphStyle("signature", parent=s["body"],
                                          fontName="Helvetica-Bold")))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=1.5 * cm, bottomMargin=1.4 * cm,
        title=f"Lettre de motivation — {user.full_name} — {job.title}",
        author=user.full_name,
    )
    doc.build(story)
    return buffer.getvalue()
