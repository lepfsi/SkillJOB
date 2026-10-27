#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""4 profils ATS 1 colonne pour LinkedIn : Support, Sécurité, Infrastructure Réseaux Systèmes Sécurité, Informaticien Généraliste.
Texte linéaire lisible par les ATS, titres de sections standards, mots-clés denses (offres montées par IA),
projets et livres sélectionnés selon la pertinence de chaque profil, liens cliquables, sans tiret long."""
import os
from fpdf import FPDF
from PIL import Image, ImageDraw

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE_DIR, "ATS_Profils")
PHOTO_SRC = os.path.join(BASE_DIR, "20260116_085939.jpg")
PHOTO = os.path.join(OUT, "photo_ats.png")

NAVY = (10, 17, 40)
TURQ = (43, 217, 197)
TURQ_D = (20, 140, 125)
INK = (22, 28, 38)
GRAY = (80, 95, 112)

ML, MR = 18, 18  # marges gauche et droite équivalentes
CW = 210 - ML - MR

FORMATION = [
    "Diplôme d'Ingénieur en Cybersécurité et Investigations Numériques, École Nationale Supérieure Polytechnique de Yaoundé (ENSPY), 2020 - 2023.",
    "Mathématiques Pures, Université de Ngaoundéré, 2017 - 2020.",
    "Baccalauréat Scientifique, Lycée Classique et Moderne de Maroua, 2017.",
]


def fonts(p):
    p.add_font("AU", "", "C:/WINDOWS/Fonts/arial.ttf")
    p.add_font("AU", "B", "C:/WINDOWS/Fonts/arialbd.ttf")
    p.add_font("AU", "I", "C:/WINDOWS/Fonts/ariali.ttf")
    p.add_font("AU", "BI", "C:/WINDOWS/Fonts/arialbi.ttf")


def photo_ats():
    """Photo ronde, anneau turquoise, fond blanc, adaptée a une page ATS claire."""
    im = Image.open(PHOTO_SRC).convert("RGB")
    w, h = im.size
    s = min(int(w * 0.72), h)  # carré plus serré que la pleine largeur : moins de plafond
    cx = int(w * 0.52)  # visage légèrement à droite du centre
    l = min(max(0, cx - s // 2), w - s)
    t = max(0, min(int(h * 0.41), h - s))  # marge au-dessus de la tête : elle ne touche plus le cercle
    im = im.crop((l, t, l + s, t + s)).resize((520, 520), Image.LANCZOS)
    m = Image.new("L", (520, 520), 0)
    ImageDraw.Draw(m).ellipse((0, 0, 520, 520), fill=255)
    b = 14
    tot = 520 + b * 2
    fin = Image.new("RGB", (tot, tot), (255, 255, 255))
    ImageDraw.Draw(fin).ellipse((0, 0, tot - 1, tot - 1), fill=TURQ)
    fin.paste(im, (b, b), m)
    fin.save(PHOTO)
    return PHOTO


def header(pdf, titre, domaines):
    ph = photo_ats()
    pdf.image(ph, x=170, y=8, w=33, h=33)  # photo légèrement décalée à droite, vers le coin
    # 1. Nom d'abord : identification immédiate (recommandation internationale)
    pdf.set_xy(ML, 8.5)
    pdf.set_font("AU", "B", 19)
    pdf.set_text_color(*NAVY)
    pdf.cell(145, 8, "STEVE BA-NDOUWE")
    # 2. Titre cible en dessous, mis en valeur par la couleur, taille auto ajustée
    pdf.set_font("AU", "B", 16)
    size = 16
    while pdf.get_string_width(titre) > 146 and size > 11:
        size -= 0.5
        pdf.set_font("AU", "B", size)
    pdf.set_xy(ML, 17)
    pdf.set_text_color(*TURQ_D)
    pdf.cell(145, 6.5, titre)
    # 3. Domaines
    pdf.set_xy(ML, 24.5)
    pdf.set_font("AU", "B", 7.8)
    pdf.set_text_color(*GRAY)
    pdf.cell(145, 4.5, domaines)
    pdf.set_xy(ML, 29.5)
    pdf.set_font("AU", "", 8.6)
    pdf.set_text_color(*INK)
    pdf.write(4.8, "+237 654 489 649   |   ")
    pdf.set_text_color(*TURQ_D)
    pdf.write(4.8, "steve.ba-ndouwe@dailyops.tech", link="mailto:steve.ba-ndouwe@dailyops.tech")
    pdf.set_text_color(*INK)
    pdf.write(4.8, "   |   Yaoundé, Cameroun")
    # 4. Liens avec libellés, plus professionnels
    pdf.set_xy(ML, 34.8)
    pdf.set_font("AU", "B", 8.2)
    pdf.set_text_color(*NAVY)
    pdf.write(4.6, "LinkedIn : ")
    pdf.set_text_color(*TURQ_D)
    pdf.write(4.6, "linkedin.com/in/stv-bnd-776ab11ba", link="https://www.linkedin.com/in/stv-bnd-776ab11ba")
    pdf.set_text_color(*GRAY)
    pdf.write(4.6, "  |  ")
    pdf.set_font("AU", "B", 8.2)
    pdf.set_text_color(*NAVY)
    pdf.write(4.6, "GitHub : ")
    pdf.set_text_color(*TURQ_D)
    pdf.write(4.6, "github.com/lepfsi", link="https://github.com/lepfsi")
    pdf.set_text_color(*GRAY)
    pdf.write(4.6, "  |  ")
    pdf.set_font("AU", "B", 8.2)
    pdf.set_text_color(*NAVY)
    pdf.write(4.6, "Site : ")
    pdf.set_text_color(*TURQ_D)
    pdf.write(4.6, "dailyops.tech", link="https://dailyops.tech")
    pdf.set_xy(ML, 40)
    pdf.set_font("AU", "", 8.2)
    pdf.set_text_color(*GRAY)
    pdf.write(4.6, "Disponible immédiatement   |   Mobilité nationale et internationale   |   Promoteur de ")
    pdf.set_text_color(*TURQ_D)
    pdf.write(4.6, "DailyOps.Tech", link="https://dailyops.tech")
    pdf.set_y(47)


def sec(pdf, t):
    pdf.ln(1.2)
    pdf.set_font("AU", "B", 11)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 6, t.upper())
    y = pdf.get_y() + 6
    pdf.set_fill_color(*TURQ)
    pdf.rect(ML, y, 16, 1.4, style="F")
    pdf.set_y(y + 3.4)


def par(pdf, t):
    pdf.set_font("AU", "", 9)
    pdf.set_text_color(*INK)
    pdf.multi_cell(CW, 4.6, t, align="J")
    pdf.ln(1.2)


def bullet(pdf, t):
    if pdf.get_y() > 279:  # garde : pas de tiret orphelin ni de page vide
        pdf.add_page()
    pdf.set_xy(ML, pdf.get_y())
    pdf.set_text_color(*TURQ_D)
    pdf.set_font("AU", "B", 9)
    pdf.cell(4.5, 4.4, "-")
    pdf.set_xy(ML + 4.5, pdf.get_y())
    pdf.set_text_color(*INK)
    pdf.set_font("AU", "", 9)
    pdf.multi_cell(CW - 4.5, 4.4, t, align="J")
    pdf.ln(0.7)


def skills(pdf, groups):
    for label, kws in groups:
        pdf.set_font("AU", "", 9)
        pdf.set_text_color(*INK)
        pdf.multi_cell(CW, 4.6, "**" + label + "** : " + kws, markdown=True, align="J")
        pdf.ln(1.7)
    pdf.ln(0.8)


def job(pdf, poste, ent, lieu, per, bullets):
    pdf.set_font("AU", "B", 9.6)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 5, poste)
    pdf.ln(5)
    pdf.set_font("AU", "", 8.6)
    pdf.set_text_color(*TURQ_D)
    pdf.write(4.4, ent)
    pdf.set_text_color(*GRAY)
    pdf.write(4.4, "  -  " + lieu + "  |  " + per)
    pdf.ln(5.2)
    for b in bullets:
        bullet(pdf, b)
    pdf.ln(1.2)


def projets(pdf, intro, items):
    pdf.set_font("AU", "I", 8.6)
    pdf.set_text_color(*GRAY)
    pdf.multi_cell(CW, 4.4, intro, align="L")
    pdf.ln(1)
    for nom, lien, d in items:
        if pdf.get_y() > 279:  # garde : l'item démarre avec assez de place, pas de page vide
            pdf.add_page()
        pdf.set_xy(ML, pdf.get_y())
        pdf.set_font("AU", "B", 9)
        pdf.set_text_color(*TURQ_D)
        pdf.cell(4.5, 4.6, "-")
        pdf.set_xy(ML + 4.5, pdf.get_y())
        pdf.set_font("AU", "", 9)
        pdf.set_text_color(*INK)
        pdf.multi_cell(CW - 4.5, 4.6, "**" + nom + "** : " + d, markdown=True, align="J", link=lien)
        pdf.ln(1.2)
    pdf.ln(0.8)


def livres(pdf, items):
    for titre, d in items:
        pdf.set_font("AU", "B", 9.2)
        pdf.set_text_color(*INK)
        pdf.write(4.6, "-  ")
        pdf.write(4.6, titre)
        pdf.set_font("AU", "I", 9)
        pdf.set_text_color(*GRAY)
        pdf.write(4.6, " : ")
        pdf.multi_cell(CW - (pdf.get_x() - ML), 4.6, d, align="J")
        pdf.ln(1.2)
    pdf.ln(0.8)


def build_profile(d):
    pdf = FPDF("P", "mm", "A4")
    fonts(pdf)
    pdf.set_auto_page_break(True, margin=12)
    pdf.set_margins(ML, 12, MR)
    pdf.set_title(d["meta"])
    pdf.set_author("Steve BA-NDOUWE")
    pdf.add_page()
    header(pdf, d["titre"], d["domaines"])
    sec(pdf, "Profil")
    par(pdf, d["profil"])
    sec(pdf, "Compétences")
    skills(pdf, d["skills"])
    sec(pdf, "Expérience professionnelle")
    for j in d["jobs"]:
        job(pdf, *j)
    sec(pdf, "Projets et écosystème DailyOps")
    projets(pdf, d["projets_intro"], d["projets"])
    if d.get("livres"):
        sec(pdf, "Publications : The Operator's Library")
        livres(pdf, d["livres"])
    sec(pdf, "Certifications")
    par(pdf, ", ".join(d["certs"]) + ".")
    sec(pdf, "Formation")
    for f in FORMATION:
        bullet(pdf, f)
    pdf.ln(0.8)
    sec(pdf, "Langues")
    par(pdf, "Français : langue maternelle. Anglais : intermédiaire.")
    out = os.path.join(OUT, d["fichier"])
    pdf.output(out)
    return out


PROFILES = {
    "support": {
        "titre": "Ingénieur Support Informatique",
        "domaines": "SUPPORT N1 N2 N3  |  SYSTÈMES  |  RÉSEAUX  |  MICROSOFT 365  |  SUPERVISION",
        "meta": "CV Steve BA-NDOUWE, Ingenieur Support Informatique, ATS",
        "fichier": "CV_STEVE_BA-NDOUWE_ATS_Ingenieur_Support.pdf",
        "profil": ("Ingénieur Support Informatique, diplômé de l'École Nationale Supérieure Polytechnique de Yaoundé. "
                   "Plus de 3 ans d'exploitation en MSP international (GOTECH Madagascar) et en banque (Société Générale Cameroun) : "
                   "support N1, N2 et N3, administration Windows Server, Active Directory et Microsoft 365, réseaux LAN et Wi-Fi, "
                   "supervision, gestion des incidents dans le respect des SLA et des procédures ITIL. "
                   "Je résous, j'explique, je documente et je fais monter les utilisateurs en compétence. Disponible immédiatement."),
        "skills": [
            ("Support et exploitation", "assistance N1, N2, N3, helpdesk, GLPI, ticketing, ITIL v4, SLA, gestion de parc, support à distance, prise en main, formation des utilisateurs, base de connaissances, reporting"),
            ("Systèmes", "Windows 10, Windows 11, Windows Server 2016 à 2022, Active Directory, GPO, DNS, DHCP, Microsoft 365, Exchange, Teams, SharePoint, Intune, WSUS, correctifs"),
            ("Réseaux", "TCP/IP, LAN, Wi-Fi, VLAN, OSPF, switches Cisco, routeurs, liens télécom, VPN d'accès, diagnostic et dépannage"),
            ("Supervision et outils", "Zabbix, Grafana, Uptime Kuma, PowerShell, Python, NAKIVO, Veeam, Kaspersky Endpoint Security"),
            ("Cloud et bureautique", "Azure, Microsoft 365, Google Workspace, suites Office, impression, périphériques, mobilité"),
        ],
        "jobs": [
            ("Ingénieur Support Infrastructures et Sécurité", "GOTECH Madagascar", "Antananarivo, Madagascar", "Août 2024 - Mai 2026", [
                "Support N2 et N3 multi clients : prise en charge des incidents systèmes, réseaux et applicatifs, résolution, escalade et reporting régulier.",
                "Installation et maintenance des postes, serveurs et équipements : préparation, images, correctifs, antivirus, périphériques et liens télécom.",
                "Administration des environnements utilisateurs : Active Directory, Microsoft 365, messagerie, partages, impression et VPN d'accès distant.",
                "Supervision Zabbix, Grafana et Uptime Kuma : détection précoce, intervention avant impact, procédures et documentation d'exploitation.",
            ]),
            ("Assistant Ingénieur Sécurité", "ENIX SARL", "Yaoundé, Cameroun", "Mars 2023 - 2024", [
                "Assistance aux missions de sécurité opérationnelle : supervision, détection et analyse des incidents.",
                "Monitoring réseau, rédaction de rapports et de recommandations pour les clients.",
            ]),
            ("Stagiaire Support IT", "Société Générale Cameroun", "Douala, Cameroun", "Août - Oct. 2022", [
                "Support utilisateurs et exploitation quotidienne des systèmes et réseaux en environnement bancaire.",
                "Traitement des incidents, matériel, messagerie, respect des procédures et des environnements critiques.",
            ]),
        ],
        "projets_intro": "Code public, documentation tenue, sélection adaptée au poste.",
        "projets": [
            ("OpsDoc", None, "documentation d'infrastructure versionnée dans Git, générée depuis des constats datés : source et statut annoncés, incertitude visible."),
            ("DailyOps.Tech", "https://dailyops.tech", "base de connaissances publique : notes de terrain, runbooks et retours d'incidents, avec labs pour tester les méthodes avant la production."),
        ],
        "livres": [
            ("The Complexity Trap", "pourquoi les systèmes deviennent plus durs à opérer, et comment reprendre la main."),
            ("The Operator's Last Job", "ce qui reste humain quand la machine exécute : support, méthode et transmission."),
        ],
        "certs": ["Kaspersky Endpoint Security", "Kaspersky Security Center MSP", "Kaspersky Next Presales", "NAKIVO Technical Certified", "Azure Administrator", "Azure Security Technologies", "Fortinet Certified Associate", "Huawei HCIA Security", "IBM IT Fundamentals Cybersecurity"],
    },
    "securite": {
        "titre": "Ingénieur Cybersécurité",
        "domaines": "CYBERSÉCURITÉ  |  NGFW  |  SIEM  |  IAM  |  CLOUD  |  CONFORMITÉ",
        "meta": "CV Steve BA-NDOUWE, Ingenieur Cybersecurite, ATS",
        "fichier": "CV_STEVE_BA-NDOUWE_ATS_Ingenieur_Securite.pdf",
        "profil": ("Ingénieur Cybersécurité et Investigations Numériques, diplômé de l'École Nationale Supérieure Polytechnique de Yaoundé (ENSPY). "
                   "Plus de 3 ans d'opérationnel en MSP international (GOTECH Madagascar) et en banque (Société Générale Cameroun) : "
                   "sécurisation des périmètres avec pare-feux NGFW, exploitation EDR Kaspersky, supervision SIEM, gestion des incidents N2 et N3, "
                   "IAM sur Azure et Microsoft 365, sauvegarde et continuité d'activité. Référentiels ISO 27001, NIS2 et ITIL. "
                   "Je détecte, j'analyse, je corrige et je documente, avec le réflexe conformité. Disponible immédiatement."),
        "skills": [
            ("Sécurité réseau", "pare-feux NGFW FortiGate, Checkpoint, Huawei, Cisco Firepower, ASA, IDS/IPS, VPN SSL et IPSec, inspection SSL, segmentation, ACL, QoS"),
            ("Endpoint et détection", "Kaspersky Endpoint Security, EDR, Microsoft Defender, durcissement, GPO, gestion des correctifs, principe de moindre privilège"),
            ("Supervision et SIEM", "Zabbix, Nagios, Grafana, Prometheus, Wazuh, corrélation des événements, qualification des alertes, réponse aux incidents N2 et N3, rapports post-incident"),
            ("IAM et cloud", "Azure, Entra ID, Microsoft 365, Active Directory, MFA, gestion des identités et des accès, comptes à privilèges"),
            ("Gouvernance et continuité", "ISO 27001, NIS2, SOC 2, ITIL, analyse de risques, PCA, PRA, sauvegarde NAKIVO, Veeam, LTO, sensibilisation des utilisateurs"),
            ("IA", "sécurité des usages de l'IA générative, DLP, détection de secrets, réécriture sûre, score de risque"),
        ],
        "jobs": [
            ("Ingénieur Support Infrastructures et Sécurité", "GOTECH Madagascar", "Antananarivo, Madagascar", "Août 2024 - Mai 2026", [
                "Sécurité périmétrique multi clients : pare-feux NGFW FortiGate, Checkpoint, Huawei et Cisco Firepower, règles de filtrage, inspection SSL, IDS/IPS et VPN.",
                "Kaspersky Endpoint Security for Business : déploiement, politiques centralisées, détection et réponse.",
                "Supervision SIEM Zabbix, Nagios, Grafana, Prometheus : qualification des alertes, analyse, escalade N2 et N3, rapports post-incident.",
                "IAM sur Azure et Microsoft 365 : identités, accès et MFA. Sauvegarde NAKIVO, Veeam et LTO, contribution aux PCA et PRA.",
            ]),
            ("Assistant Ingénieur Sécurité", "ENIX SARL", "Yaoundé, Cameroun", "Mars 2023 - 2024", [
                "Cybersécurité opérationnelle : supervision, détection et analyse des incidents.",
                "Analyses de risques IT et recommandations concrètes : firewall, VPN, sauvegarde, contrôle des accès.",
            ]),
            ("Stagiaire Support IT", "Société Générale Cameroun", "Douala, Cameroun", "Août - Oct. 2022", [
                "Exploitation quotidienne des systèmes et réseaux en contexte bancaire.",
                "Premiers repères de sécurité et de conformité propres au secteur financier.",
            ]),
        ],
        "projets_intro": "Code public, documentation tenue, sélection adaptée au poste.",
        "projets": [
            ("OpsGate", "https://github.com/lepfsi/ops-gate", "passerelle de sécurité pour l'IA générative : détection des secrets et des données sensibles, réécriture sûre et score de risque, contrôle local par défaut."),
            ("OpsVault", None, "coffre de secrets à chiffrement côté client : accès courts et tracés pour les agents IA, aucun secret en clair côté serveur."),
            ("OpsInsight", None, "corrélation des signaux Zabbix, Prometheus, Wazuh et des journaux : cause probable et action suggérée, pensé pour ISO 27001, NIS2 et SOC 2."),
        ],
        "livres": [
            ("Beyond the Firewall", "voir le système réel derrière les écrans."),
            ("Security in the Age of AI", "la sécurité quand l'attaque et la défense raisonnent."),
        ],
        "certs": ["Fortinet Certified Associate", "Huawei HCIA Security", "IBM IT Fundamentals Cybersecurity", "Kaspersky Endpoint Security", "Kaspersky Security Center MSP", "Kaspersky Next Presales", "Azure Administrator", "Azure Security Technologies", "NAKIVO Technical Certified"],
    },
    "infrastructure": {
        "titre": "Ingénieur Infrastructure, Réseaux et Sécurité",
        "domaines": "RÉSEAUX  |  SYSTÈMES  |  VIRTUALISATION  |  SÉCURITÉ  |  SUPERVISION",
        "meta": "CV Steve BA-NDOUWE, Ingenieur Infrastructure Reseaux et Securite, ATS",
        "fichier": "CV_STEVE_BA-NDOUWE_ATS_Infrastructure_Reseaux_Securite.pdf",
        "profil": ("Ingénieur Infrastructure, Réseaux et Sécurité, diplômé de l'École Nationale Supérieure Polytechnique de Yaoundé. "
                   "Plus de 3 ans à déployer et exploiter des infrastructures multi sites en MSP international (GOTECH Madagascar) et en banque "
                   "(Société Générale Cameroun) : switching et routage, pare-feux NGFW, Windows Server et Active Directory, virtualisation VMware, "
                   "Proxmox et Hyper-V, SAN, sauvegarde et PCA/PRA, supervision Zabbix et Grafana. La sécurité est intégrée à chaque couche, "
                   "avec les repères ISO 27001 et ITIL. Disponible immédiatement."),
        "skills": [
            ("Réseaux", "switching, routage OSPF et BGP, VLAN, STP, ACL, QoS, Wi-Fi, SD-WAN, liens télécom, TCP/IP, VPN site à site, switches Cisco, Juniper, Aruba"),
            ("Sécurité réseau", "pare-feux NGFW FortiGate, Checkpoint, Huawei, Cisco Firepower, IDS/IPS, inspection SSL, VPN SSL et IPSec, PKI, certificats SSL, segmentation"),
            ("Systèmes", "Windows Server 2016 à 2022, Active Directory, GPO, DNS, DHCP, messagerie, Linux Ubuntu et Debian, script PowerShell"),
            ("Virtualisation et stockage", "VMware ESXi, vCenter, Proxmox, Hyper-V, SAN HPE et Dell, NAS, clusters, migrations, serveurs HPE, Dell, SuperMicro"),
            ("Sauvegarde et continuité", "NAKIVO, Veeam, LTO, PCA, PRA, tests de restauration, haute disponibilité, surveillance production et secours"),
            ("Supervision et cloud", "Zabbix, Nagios, Grafana, Prometheus, Uptime Kuma, Azure, Microsoft 365, ISO 27001, ITIL"),
        ],
        "jobs": [
            ("Ingénieur Support Infrastructures et Sécurité", "GOTECH Madagascar", "Antananarivo, Madagascar", "Août 2024 - Mai 2026", [
                "Déploiement et exploitation d'infrastructures multi sites et multi clients : réseaux, systèmes, virtualisation et sécurité.",
                "Réseaux : switches, routage OSPF et BGP, VLAN, QoS, liens télécom et SD-WAN, pare-feux NGFW FortiGate, Checkpoint, Huawei et Cisco Firepower, VPN site à site.",
                "Systèmes : Windows Server, Active Directory, GPO, DNS, DHCP, messagerie, correctifs, Linux. Virtualisation VMware ESXi, Proxmox, Hyper-V, SAN.",
                "Sauvegarde et continuité : NAKIVO, Veeam et LTO, surveillance production et secours, contribution aux PCA et PRA. Supervision Zabbix, Prometheus et Grafana.",
            ]),
            ("Assistant Ingénieur Sécurité", "ENIX SARL", "Yaoundé, Cameroun", "Mars 2023 - 2024", [
                "Participation aux projets clients : audit technique, monitoring réseau et mise en œuvre des recommandations.",
                "Supervision, détection et analyse des incidents, rapports d'exploitation.",
            ]),
            ("Stagiaire Support IT", "Société Générale Cameroun", "Douala, Cameroun", "Août - Oct. 2022", [
                "Exploitation quotidienne des systèmes et réseaux bancaires : disponibilité, procédures, environnements critiques.",
                "Découverte des exigences de sécurité et de continuité du secteur financier.",
            ]),
        ],
        "projets_intro": "Code public, documentation tenue, sélection adaptée au poste.",
        "projets": [
            ("OpsInsight", None, "corrélation des signaux Zabbix, Prometheus, Wazuh et des journaux : cause probable et action suggérée."),
            ("OpsDoc", None, "documentation d'infrastructure versionnée dans Git : chaque collecte annonce sa source et son statut."),
            ("DailyOps.Tech", "https://dailyops.tech", "runbooks et labs : méthodes testées avant production."),
        ],
        "livres": [
            ("Beyond the Firewall", "voir le système réel derrière les écrans."),
            ("The Complexity Trap", "pourquoi les systèmes deviennent plus durs à opérer, et comment reprendre la main."),
        ],
        "certs": ["Azure Administrator", "Azure Security Technologies", "Fortinet Certified Associate", "Huawei HCIA Security", "NAKIVO Technical Certified", "Kaspersky Endpoint Security", "Kaspersky Security Center MSP", "IBM IT Fundamentals Cybersecurity"],
    },
    "informaticien": {
        "titre": "Ingénieur Systèmes, Réseaux et Support IT",
        "domaines": "SYSTÈMES  |  RÉSEAUX  |  SUPPORT IT  |  SÉCURITÉ  |  SCRIPTS  |  M365",
        "meta": "CV Steve BA-NDOUWE, Ingenieur Systemes Reseaux et Support IT, ATS",
        "fichier": "CV_STEVE_BA-NDOUWE_ATS_Ingenieur_Systemes_Reseaux_Support_IT.pdf",
        "profil": ("Ingénieur Systèmes, Réseaux et Support IT, diplômé de l'École Nationale Supérieure Polytechnique de Yaoundé. "
                   "Plus de 3 ans en MSP international (GOTECH Madagascar) et en banque (Société Générale Cameroun) : support utilisateurs, "
                   "systèmes Windows et Linux, réseaux, Microsoft 365, sécurité, sauvegarde, scripts PowerShell et Python. "
                   "Polyvalent et autonome, à l'aise du poste de travail au serveur, avec un goût marqué pour la documentation et la transmission. "
                   "Disponible immédiatement."),
        "skills": [
            ("Support et utilisateurs", "assistance N1 et N2, helpdesk, GLPI, formation des utilisateurs, bureautique, Microsoft 365, matériel, périphériques, impression"),
            ("Systèmes et réseaux", "Windows, Linux, Active Directory, Microsoft 365, TCP/IP, LAN, Wi-Fi, VLAN, switches, routeurs, VPN, liens télécom"),
            ("Développement et scripts", "Python, PowerShell, SQL, HTML, CSS, WordPress, API REST, automatisation des tâches"),
            ("Sécurité et sauvegarde", "antivirus Kaspersky, MFA, bonnes pratiques, sauvegardes NAKIVO et Veeam, sensibilisation des utilisateurs"),
            ("Virtualisation et cloud", "VMware ESXi, Proxmox, Hyper-V, Azure, Microsoft 365, Google Workspace"),
            ("Méthodes et gestion", "ITIL, gestion de parc, inventaire, documentation, procédures, reporting, suivi de projets"),
        ],
        "jobs": [
            ("Ingénieur Support Infrastructures et Sécurité", "GOTECH Madagascar", "Antananarivo, Madagascar", "Août 2024 - Mai 2026", [
                "Polyvalence opérationnelle en MSP international : support utilisateurs N1 à N3, systèmes, réseaux, sécurité et sauvegarde pour des clients multi sites.",
                "Administration Windows Server, Active Directory, Microsoft 365 et messagerie : comptes, accès, correctifs, antivirus, renouvellement de parc.",
                "Réseaux : switches, Wi-Fi, VLAN, liens télécom et VPN. Supervision Zabbix, Grafana et Uptime Kuma. Scripts PowerShell et Python pour l'automatisation.",
                "Sauvegardes NAKIVO et Veeam avec tests de restauration, documentation et procédures d'exploitation.",
            ]),
            ("Assistant Ingénieur Sécurité", "ENIX SARL", "Yaoundé, Cameroun", "Mars 2023 - 2024", [
                "Missions variées pour les clients : supervision, analyse de risques, rédaction de rapports et de recommandations.",
                "Support technique et suivi des actions correctives.",
            ]),
            ("Stagiaire Support IT", "Société Générale Cameroun", "Douala, Cameroun", "Août - Oct. 2022", [
                "Support utilisateurs et exploitation des systèmes et réseaux en banque, dans le respect des procédures.",
                "Premiers repères de conformité et d'environnements critiques.",
            ]),
        ],
        "projets_intro": "Code public, documentation tenue, sélection adaptée au poste.",
        "projets": [
            ("OpsDoc", None, "documentation versionnée dans Git, générée depuis des constats datés : source et statut annoncés."),
            ("DailyOps.Tech", "https://dailyops.tech", "base de connaissances publique : notes de terrain, runbooks, retours d'incidents et labs."),
        ],
        "livres": [
            ("The Human Single Point of Failure", "quand tout repose sur une seule personne, et comment s'en prémunir."),
            ("The Operator's Last Job", "ce qui reste humain quand la machine exécute."),
        ],
        "certs": ["Azure Administrator", "Kaspersky Endpoint Security", "Kaspersky Security Center MSP", "NAKIVO Technical Certified", "Fortinet Certified Associate", "Huawei HCIA Security", "IBM IT Fundamentals Cybersecurity"],
    },
}


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for key in ["support", "securite", "infrastructure", "informaticien"]:
        print(key, "->", build_profile(PROFILES[key]))
