#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Versions 2 colonnes pour lecture RH directe : Support, Sécurité, Infrastructure Réseaux Sécurité,
Ingénieur Systèmes Réseaux Support IT. Design charte DailyOps (bandeau navy, barre latérale, cadres).
Largeurs contraintes (aucun texte ne traverse les colonnes), hauteurs mesurées avant chaque saut de
page (l'espace est rempli tant qu'un bloc tient), barre latérale fluide par sections ajustables."""
import os
from fpdf import FPDF
from PIL import Image, ImageDraw
from generate_ats_profils import PROFILES, FORMATION, PHOTO_SRC, fonts
from generate_ats_profils import NAVY, TURQ, TURQ_D, INK, GRAY

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE_DIR, "RH_2colonnes")
PHOTO = os.path.join(OUT, "photo_rh.png")

SIDE_BG = (238, 244, 243)
WHITE = (255, 255, 255)

LX, LW = 8, 58          # colonne latérale
RX, RW = 71, 131        # colonne principale
TOP = 55
SB_W = 68               # largeur du fond de barre latérale
BOTTOM = 284            # limite basse colonne principale (13 mm de marge)
SB_BOTTOM = 290         # limite basse barre latérale

# Contenus propres à la barre latérale, par profil
SIDEBAR = {
    "support": {
        "savoir": ["Support N1, N2 et N3, helpdesk", "Windows Server et Active Directory", "Microsoft 365 et messagerie",
                   "Réseaux LAN, Wi-Fi et VLAN", "Supervision Zabbix et Grafana", "Gestion de parc et GLPI",
                   "Scripts PowerShell et Python"],
        "environnements": "Windows 10 et 11, Windows Server, AD, GPO, M365, Exchange, Intune, Cisco, VPN, Zabbix, Grafana, NAKIVO, Veeam, Kaspersky, Azure, ITIL",
        "atouts": ["Rigueur et méthode", "Sens du service", "Calme en incident", "Esprit d'équipe", "Pédagogie utilisateurs"],
    },
    "securite": {
        "savoir": ["Pare-feux NGFW et IDS/IPS", "VPN SSL et IPSec", "EDR Kaspersky et Defender", "SIEM et supervision",
                   "IAM Azure et M365", "ISO 27001 et NIS2", "Analyse de risques et durcissement"],
        "environnements": "FortiGate, Checkpoint, Huawei, Cisco Firepower, Kaspersky, Wazuh, Zabbix, Grafana, Azure Entra ID, M365, NAKIVO, Veeam, ISO 27001, NIS2, SOC 2, ITIL",
        "atouts": ["Rigueur et méthode", "Réflexe conformité", "Calme en incident", "Esprit d'analyse", "Documentation systématique"],
    },
    "infrastructure": {
        "savoir": ["Réseaux : switching, OSPF, BGP", "SD-WAN et liens télécom", "Pare-feux NGFW et VPN", "Windows Server, AD, Linux",
                   "VMware, Proxmox et SAN", "Sauvegarde et PCA/PRA", "Supervision et MCO"],
        "environnements": "Cisco, Juniper, Aruba, FortiGate, Checkpoint, Huawei, Windows Server, AD, Linux, VMware, Proxmox, Hyper-V, SAN HPE et Dell, NAKIVO, Veeam, Zabbix, Azure, ITIL",
        "atouts": ["Rigueur et méthode", "Fiabilisation de l'exploitation", "Vision globale", "Calme en incident", "Esprit d'équipe"],
    },
    "informaticien": {
        "savoir": ["Support utilisateurs N1 et N2", "Windows, Linux et Active Directory", "Microsoft 365 et bureautique",
                   "Réseaux et liens télécom", "Scripts Python et PowerShell", "Sécurité et sauvegardes",
                   "Gestion de parc et documentation"],
        "environnements": "Windows, Linux, AD, M365, Google Workspace, Python, PowerShell, SQL, GLPI, VMware, Proxmox, Azure, Zabbix, NAKIVO, Veeam, Kaspersky, ITIL",
        "atouts": ["Polyvalence", "Autonomie", "Sens du service", "Rigueur et méthode", "Curiosité technique"],
    },
}

FICHIERS = {
    "support": ("CV_STEVE_BA-NDOUWE_RH_Ingenieur_Support.pdf", "CV Steve BA-NDOUWE, Ingenieur Support Informatique, 2 colonnes RH"),
    "securite": ("CV_STEVE_BA-NDOUWE_RH_Ingenieur_Securite.pdf", "CV Steve BA-NDOUWE, Ingenieur Cybersecurite, 2 colonnes RH"),
    "infrastructure": ("CV_STEVE_BA-NDOUWE_RH_Infrastructure_Reseaux_Securite.pdf", "CV Steve BA-NDOUWE, Ingenieur Infrastructure Reseaux Securite, 2 colonnes RH"),
    "informaticien": ("CV_STEVE_BA-NDOUWE_RH_Ingenieur_Systemes_Reseaux_Support_IT.pdf", "CV Steve BA-NDOUWE, Ingenieur Systemes Reseaux Support IT, 2 colonnes RH"),
}


def photo_rh():
    """Photo ronde, anneau turquoise sur fond navy : se fond dans le bandeau d'en-tête."""
    im = Image.open(PHOTO_SRC).convert("RGB")
    w, h = im.size
    s = min(int(w * 0.72), h)
    cx = int(w * 0.52)
    l = min(max(0, cx - s // 2), w - s)
    t = max(0, min(int(h * 0.41), h - s))
    im = im.crop((l, t, l + s, t + s)).resize((520, 520), Image.LANCZOS)
    m = Image.new("L", (520, 520), 0)
    ImageDraw.Draw(m).ellipse((0, 0, 520, 520), fill=255)
    b = 10
    tot = 520 + b * 2
    fin = Image.new("RGB", (tot, tot), NAVY)
    ImageDraw.Draw(fin).ellipse((0, 0, tot - 1, tot - 1), fill=TURQ)
    fin.paste(im, (b, b), m)
    fin.save(PHOTO)
    return fin and PHOTO


# ---------------------------------------------------------------- briques graphiques
def header(p, titre, domaines):
    p.set_fill_color(*NAVY)
    p.rect(0, 0, 210, 50, style="F")
    p.set_fill_color(*TURQ)
    p.rect(0, 50, 210, 1.6, style="F")
    p.image(photo_rh(), x=10, y=6, w=33, h=33)
    # nom d'abord : identification immédiate, titre cible en dessous
    p.set_xy(47, 4.5)
    p.set_text_color(*WHITE)
    p.set_font("AU", "B", 16)
    p.cell(160, 7, "STEVE BA-NDOUWE")
    p.set_font("AU", "B", 13.5)
    size = 13.5
    while p.get_string_width(titre) > 150 and size > 11:
        size -= 0.5
        p.set_font("AU", "B", size)
    p.set_xy(47, 12.5)
    p.set_text_color(*TURQ)
    p.cell(160, 5.5, titre)
    p.set_xy(47, 20)
    p.set_text_color(*TURQ)
    p.set_font("AU", "B", 7.6)
    p.cell(160, 4.5, domaines)
    p.set_xy(47, 25.5)
    p.set_text_color(*WHITE)
    p.set_font("AU", "", 7.8)
    p.write(4.5, "+237 654 489 649   |   ")
    p.set_text_color(*TURQ)
    p.write(4.5, "steve.ba-ndouwe@dailyops.tech", link="mailto:steve.ba-ndouwe@dailyops.tech")
    p.set_text_color(*WHITE)
    p.write(4.5, "   |   Yaoundé, Cameroun")
    p.set_xy(47, 30.4)
    p.set_font("AU", "", 7.8)
    p.write(4.5, "Disponible immédiatement   -   Mobilité nationale et internationale   -   Promoteur de ")
    p.set_font("AU", "B", 7.8)
    p.write(4.5, "DailyOps", link="https://dailyops.tech")
    p.set_text_color(*TURQ)
    p.write(4.5, ".Tech", link="https://dailyops.tech")
    p.set_xy(47, 35.4)
    p.set_text_color(180, 195, 210)
    p.set_font("AU", "B", 7.4)
    p.write(4.5, "LinkedIn : ")
    p.set_text_color(*TURQ)
    p.write(4.5, "linkedin.com/in/stv-bnd-776ab11ba", link="https://www.linkedin.com/in/stv-bnd-776ab11ba")
    p.set_text_color(180, 195, 210)
    p.write(4.5, "   |   ")
    p.set_font("AU", "B", 7.4)
    p.write(4.5, "GitHub : ")
    p.set_text_color(*TURQ)
    p.write(4.5, "github.com/lepfsi", link="https://github.com/lepfsi")
    p.set_text_color(180, 195, 210)
    p.write(4.5, "   |   ")
    p.set_font("AU", "B", 7.4)
    p.write(4.5, "Site : ")
    p.set_text_color(*TURQ)
    p.write(4.5, "dailyops.tech", link="https://dailyops.tech")


def side_title(p, y, t):
    p.set_xy(LX, y)
    p.set_text_color(*NAVY)
    p.set_font("AU", "B", 9)
    p.cell(LW, 5.5, t.upper())
    p.set_fill_color(*TURQ)
    p.rect(LX, y + 5.8, 16, 1.6, style="F")
    return y + 9.2


def side_text(p, y, txt, size=7.8, bold=False, color=INK, link=None):
    p.set_xy(LX, y)
    p.set_text_color(*color)
    p.set_font("AU", "B" if bold else "", size)
    if link:
        p.cell(LW, 4.4, txt, link=link)
        return y + 5
    p.multi_cell(LW, 4.3, txt)
    return p.get_y() + 0.6


def side_bullet(p, y, txt, size=7.5):
    p.set_xy(LX, y)
    p.set_text_color(*TURQ_D)
    p.set_font("AU", "B", size)
    p.cell(3.5, 4.2, "-")
    p.set_xy(LX + 3.5, y)
    p.set_text_color(*INK)
    p.set_font("AU", "", size)
    p.multi_cell(LW - 3.5, 4.2, txt)
    return p.get_y() + 0.5


def main_title(p, y, t):
    p.set_xy(RX, y)
    p.set_text_color(*NAVY)
    p.set_font("AU", "B", 11)
    p.cell(RW, 6, t.upper())
    p.set_fill_color(*TURQ)
    p.rect(RX, y + 6.5, 18, 1.8, style="F")
    return y + 10.5


# ---------------------------------------------------------------- mesures de hauteurs (split_only)
def n_lines(p, txt, w, gap, size, style=""):
    p.set_font("AU", style, size)
    return len(p.multi_cell(w, gap, txt, dry_run=True, output="LINES"))


def par_height(p, txt, size=8.4, gap=4.5):
    return n_lines(p, txt, RW, gap, size) * gap + 1.4


def job_height(p, poste, ent, lieu, per, bullets):
    total = 9.8  # ligne intitulé + ligne entreprise
    for b in bullets:
        total += n_lines(p, b, RW - 4, 4.3, 8) * 4.3 + 0.5
    return total + 2.4


def skill_box_height(p, label, kws):
    return 5.9 + n_lines(p, kws, RW - 3, 3.8, 7.4) * 3.8 + 1.2


def projet_height(p, desc):
    return 4.4 + n_lines(p, desc, RW - 4, 4.3, 8) * 4.3 + 1.8


def livre_height(p, desc):
    return 4.3 + n_lines(p, desc, RW - 4, 4.2, 7.8, style="I") * 4.2 + 1.4


# ---------------------------------------------------------------- blocs de la colonne principale
def par_just(p, y, txt, size=8.4, gap=4.5, color=INK):
    p.set_xy(RX, y)
    p.set_text_color(*color)
    p.set_font("AU", "", size)
    p.multi_cell(RW, gap, txt, align="J")
    return p.get_y() + 1.4


def numbers(p, y, nb_certs):
    bx = RX
    for num, lab in [("3+", "ans d'expérience"), (str(nb_certs), "certifications"), ("20+", "technologies")]:
        p.set_xy(bx, y)
        p.set_fill_color(234, 242, 241)
        p.rect(bx, y, 41.5, 13, style="F")
        p.set_draw_color(200, 215, 212)
        p.set_line_width(0.25)
        p.rect(bx, y, 41.5, 13, style="D")
        p.set_xy(bx, y + 1)
        p.set_text_color(*NAVY)
        p.set_font("AU", "B", 11)
        p.cell(41.5, 5, num, align="C")
        p.set_xy(bx, y + 6.8)
        p.set_font("AU", "", 7)
        p.set_text_color(*GRAY)
        p.cell(41.5, 4, lab, align="C")
        bx += 44
    p.set_line_width(0.2)
    return y + 16


def job(p, y, poste, ent, lieu, per, bullets):
    p.set_xy(RX, y)
    p.set_font("AU", "B", 9)
    p.set_text_color(*NAVY)
    p.cell(RW - 46, 5, poste)
    p.set_fill_color(*NAVY)
    p.set_text_color(*WHITE)
    p.set_font("AU", "B", 6.8)
    p.cell(46, 5, " " + per, fill=True)
    y = p.get_y() + 5
    p.set_xy(RX, y)
    p.set_font("AU", "B", 8)
    p.set_text_color(*TURQ_D)
    p.write(4.4, ent + "   ")
    p.set_text_color(*GRAY)
    p.set_font("AU", "I", 7.6)
    p.write(4.4, lieu)
    y = p.get_y() + 4.8
    for b in bullets:
        p.set_xy(RX, y)
        p.set_text_color(*TURQ_D)
        p.set_font("AU", "B", 8)
        p.cell(4, 4.3, "-")
        p.set_xy(RX + 4, y)
        p.set_text_color(*INK)
        p.set_font("AU", "", 8)
        p.multi_cell(RW - 4, 4.3, b, align="J")
        y = p.get_y() + 0.5
    return y + 2.4


def skill_box(p, y, label, kws):
    p.set_xy(RX + 1.5, y + 1)
    p.set_font("AU", "B", 7.4)
    p.set_text_color(*TURQ_D)
    p.cell(RW - 3, 3.8, label)
    p.set_xy(RX + 1.5, y + 4.9)
    p.set_font("AU", "", 7.4)
    p.set_text_color(*INK)
    p.multi_cell(RW - 3, 3.8, kws, align="J")
    y1 = p.get_y() + 1
    p.set_draw_color(208, 220, 217)
    p.set_line_width(0.25)
    p.rect(RX, y, RW, y1 - y, style="D")
    p.set_line_width(0.2)
    return y1 + 1.2


def projet(p, y, nom, lien, desc):
    p.set_xy(RX, y)
    p.set_text_color(*TURQ_D)
    p.set_font("AU", "B", 8.4)
    p.cell(4, 4.4, "-")
    p.set_xy(RX + 4, y)
    p.set_text_color(*NAVY)
    p.set_font("AU", "B", 8.4)
    p.write(4.4, nom, link=lien)
    y = p.get_y() + 4.4
    p.set_xy(RX + 4, y)
    p.set_text_color(*INK)
    p.set_font("AU", "", 8)
    p.multi_cell(RW - 4, 4.3, desc, align="J")
    return p.get_y() + 1.8


def livre(p, y, titre, desc):
    """Titre sur sa ligne (cell contraint), description justifiée sous le titre : ne traverse jamais la colonne."""
    p.set_xy(RX, y)
    p.set_text_color(*TURQ_D)
    p.set_font("AU", "B", 8)
    p.cell(4, 4.3, "-")
    p.set_xy(RX + 4, y)
    p.set_text_color(*NAVY)
    p.set_font("AU", "B", 8)
    p.cell(RW - 4, 4.3, titre)
    p.set_xy(RX + 4, y + 4.3)
    p.set_text_color(*GRAY)
    p.set_font("AU", "I", 7.8)
    p.multi_cell(RW - 4, 4.2, desc, align="J")
    return p.get_y() + 1.4


# ---------------------------------------------------------------- barre latérale fluide
def make_sections(key, d, sb):
    """Sections de la barre latérale, dans l'ordre de priorité. Chaque section est un bloc insécable."""
    it = lambda t, **kw: ("text", t, kw)
    bl = lambda t, **kw: ("bullet", t, kw)
    return [
        {"title": "Contact", "items": [
            it("+237 654 489 649"),
            it("steve.ba-ndouwe@dailyops.tech", color=TURQ_D, link="mailto:steve.ba-ndouwe@dailyops.tech"),
            it("Yaoundé, Cameroun"),
            it("Disponibilité immédiate", bold=True, color=NAVY),
            it("Mobilité nationale et internationale"),
        ]},
        {"title": "Savoir faire", "items": [bl(s) for s in sb["savoir"]]},
        {"title": "Certifications", "items": [bl(s, size=7.3) for s in d["certs"]]},
        {"title": "Formation", "items": [it(s, size=7.3) for s in FORMATION]},
        {"title": "Langues", "items": [it("Français : langue maternelle"), it("Anglais : intermédiaire")]},
        {"title": "Atouts", "items": [bl(s) for s in sb["atouts"]]},
        {"title": "Environnements", "items": [it(sb["environnements"], size=7.2, color=GRAY)]},
        {"title": "En ligne", "items": [
            it("dailyops.tech", color=TURQ_D, link="https://dailyops.tech"),
            it("github.com/lepfsi", color=TURQ_D, link="https://github.com/lepfsi"),
        ]},
    ]


def block_height(p, b):
    kind, txt, kw = b
    if kind == "text":
        if kw.get("link"):
            return 5.0
        size = kw.get("size", 7.8)
        return n_lines(p, txt, LW, 4.3, size, style="B" if kw.get("bold") else "") * 4.3 + 0.6
    return n_lines(p, txt, LW - 3.5, 4.2, kw.get("size", 7.5)) * 4.2 + 0.5


def draw_block(p, b, y):
    kind, txt, kw = b
    if kind == "text":
        return side_text(p, y, txt, **kw)
    return side_bullet(p, y, txt, **kw)


def section_height(p, sec):
    return 9.2 + sum(block_height(p, b) for b in sec["items"])


def draw_sidebar(p, sections, y, y_limit):
    """Remplit l'espace : chaque section qui tient est dessinée, celles qui ne tiennent pas passent
    à la page suivante (une section plus bas peut prendre la place laissée libre)."""
    rest = []
    first = True
    for sec in sections:
        gap = 0 if first else 2
        if y + gap + section_height(p, sec) > y_limit:
            rest.append(sec)
            continue
        y += gap
        p.set_xy(LX, y)
        y = side_title(p, y, sec["title"])
        for b in sec["items"]:
            y = draw_block(p, b, y)
        first = False
    return y, rest


# ---------------------------------------------------------------- assemblage
def build(key):
    d = PROFILES[key]
    sb = SIDEBAR[key]
    fichier, meta = FICHIERS[key]
    p = FPDF("P", "mm", "A4")
    fonts(p)
    p.set_auto_page_break(False)  # pagination manuelle : évite les pages vides
    p.set_margins(10, 10, 10)
    p.set_title(meta)
    p.set_author("Steve BA-NDOUWE")
    p.add_page()
    header(p, d["titre"], d["domaines"])

    state = {"rest": make_sections(key, d, sb), "y": TOP}

    def new_page():
        p.add_page()
        p.set_fill_color(*SIDE_BG)
        p.rect(0, 0, SB_W, 297, style="F")
        p.set_fill_color(*TURQ)
        p.rect(SB_W, 0, 1.4, 297, style="F")
        state["y"], state["rest"] = draw_sidebar(p, state["rest"], 10, SB_BOTTOM)
        return 10

    def guard(y, need):
        if y + need > BOTTOM:
            return new_page()
        return y

    # fond de barre latérale page 1 puis remplissage fluide
    p.set_fill_color(*SIDE_BG)
    p.rect(0, 51.6, SB_W, 245.4, style="F")
    p.set_fill_color(*TURQ)
    p.rect(SB_W, 51.6, 1.4, 245.4, style="F")
    state["y"], state["rest"] = draw_sidebar(p, state["rest"], TOP, SB_BOTTOM)

    # ----- colonne principale, sauts de page seulement quand le bloc réel ne tient plus
    y = TOP
    y = main_title(p, y, "Profil")
    y = par_just(p, y, d["profil"])
    y = numbers(p, y, len(d["certs"]))

    y = guard(y, 10.5 + job_height(p, *d["jobs"][0]))
    y = main_title(p, y, "Expérience professionnelle")
    for j in d["jobs"]:
        y = guard(y, job_height(p, *j))
        y = job(p, y, *j)

    y = guard(y, 10.5 + skill_box_height(p, *d["skills"][0]))
    y = main_title(p, y, "Compétences techniques")
    for label, kws in d["skills"]:
        y = guard(y, skill_box_height(p, label, kws))
        y = skill_box(p, y, label, kws)

    y = guard(y, 10.5 + par_height(p, d["projets_intro"], 8, 4.3))
    y = main_title(p, y, "Projets et écosystème DailyOps")
    y = par_just(p, y, d["projets_intro"], size=8, gap=4.3, color=GRAY)
    for item in d["projets"]:
        y = guard(y, projet_height(p, item[2]))
        y = projet(p, y, *item)

    if d.get("livres"):
        y = guard(y, 10.5 + livre_height(p, d["livres"][0][1]))
        y = main_title(p, y, "Publications : The Operator's Library")
        for t, desc in d["livres"]:
            y = guard(y, livre_height(p, desc))
            y = livre(p, y, t, desc)

    # barre latérale : la suite se place sur la dernière page, ou sur une nouvelle si pleine
    while state["rest"]:
        state["y"], state["rest"] = draw_sidebar(p, state["rest"], state["y"], SB_BOTTOM)
        if state["rest"]:
            new_page()

    out = os.path.join(OUT, fichier)
    p.output(out)
    return out


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for k in ["support", "securite", "infrastructure", "informaticien"]:
        print(k, "->", build(k))
