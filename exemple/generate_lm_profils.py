#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lettres de motivation pour les 4 profils : Support, Sécurité, Infrastructure Réseaux Sécurité,
Ingénieur Systèmes Réseaux Support IT. Modèles prêts à adapter : [ENTREPRISE], [ADRESSE], [VILLE]
sont remplacés automatiquement quand on passe entreprise=... à build_lm(). Charte DailyOps :
bandeau navy, objet gras souligné turquoise, corps justifié, signature à droite, une page."""
import os
import datetime
from fpdf import FPDF
from generate_ats_profils import fonts
from generate_ats_profils import NAVY, TURQ, TURQ_D, INK, GRAY

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE_DIR, "LM_Profils")

ML = 18               # marge gauche
XD = 118              # début colonne droite (destinataire, date, signature)
WD = 210 - 15 - XD    # largeur colonne droite
LARG = 210 - ML - 15  # largeur utile
WO = int(210 / 2) - ML  # largeur objet : retour à la ligne au milieu de la page

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

CLOSING = ("Disponible immédiatement et mobile, je serais heureux de développer ma candidature "
           "lors d'un entretien. Je vous prie d'agréer, Madame, Monsieur, l'expression de mes "
           "salutations distinguées.")

LM_DATA = {
    "support": {
        "poste": "Ingénieur Support Informatique",
        "objet": "Candidature au poste d'Ingénieur Support Informatique",
        "fichier": "LM_STEVE_BA-NDOUWE_Ingenieur_Support.pdf",
        "paras": [
            "Je candidate au poste d'Ingénieur Support Informatique au sein de [ENTREPRISE]. "
            "Ingénieur diplômé de l'École Nationale Supérieure Polytechnique de Yaoundé, j'interviens "
            "depuis plus de 3 ans en support N1, N2 et N3, en MSP international et en banque. "
            "Je résous, j'explique, je documente et je fais monter les utilisateurs en compétence.",
            "Chez GOTECH Madagascar, j'ai pris en charge les incidents systèmes, réseaux et applicatifs "
            "de clients multi sites : administration Windows Server, Active Directory et Microsoft 365, "
            "préparation et maintenance des postes, supervision Zabbix et Grafana, escalade et reporting "
            "dans le respect des SLA. Chez ENIX SARL, j'ai structuré le monitoring et les rapports "
            "d'incidents. Mon stage à la Société Générale Cameroun m'a appris la rigueur des "
            "environnements bancaires.",
            "Pour [ENTREPRISE], je m'engage sur la disponibilité des services et la satisfaction des "
            "utilisateurs : réponse rapide, résolution durable, méthode ITIL, documentation et formation "
            "qui réduisent les incidents récurrents. OpsDoc, mon projet de documentation versionnée "
            "publié sur DailyOps.Tech, illustre cette approche.",
            CLOSING,
        ],
    },
    "securite": {
        "poste": "Ingénieur Cybersécurité",
        "objet": "Candidature au poste d'Ingénieur Cybersécurité",
        "fichier": "LM_STEVE_BA-NDOUWE_Ingenieur_Securite.pdf",
        "paras": [
            "Je candidate au poste d'Ingénieur Cybersécurité au sein de [ENTREPRISE]. Ingénieur "
            "Cybersécurité et Investigations Numériques, diplômé de l'École Nationale Supérieure "
            "Polytechnique de Yaoundé (ENSPY), j'opère depuis plus de 3 ans en MSP international et en "
            "banque. Je détecte, j'analyse, je corrige et je documente, avec le réflexe conformité.",
            "Chez GOTECH Madagascar, j'ai sécurisé des périmètres multi clients : pare-feux NGFW "
            "FortiGate, Checkpoint, Huawei et Cisco Firepower, EDR Kaspersky, supervision SIEM Zabbix et "
            "Prometheus, incidents N2 et N3, IAM sur Azure et Microsoft 365, sauvegarde et continuité. "
            "Chez ENIX SARL, j'ai mené les analyses de risques et la réponse aux incidents. Je construis "
            "aussi OpsGate, sécurité des usages de l'IA générative, et OpsVault, coffre de secrets à "
            "chiffrement côté client, deux projets publics référencés sur DailyOps.Tech.",
            "Pour [ENTREPRISE], j'apporte une pratique opérationnelle ancrée dans les référentiels "
            "ISO 27001, NIS2 et ITIL : durcissement des accès, supervision lisible, réponse aux incidents "
            "et pédagogie auprès des équipes, car une sécurité inutilisable finit toujours par être "
            "contournée.",
            CLOSING,
        ],
    },
    "infrastructure": {
        "poste": "Ingénieur Infrastructure, Réseaux et Sécurité",
        "objet": "Candidature au poste d'Ingénieur Infrastructure, Réseaux et Sécurité",
        "fichier": "LM_STEVE_BA-NDOUWE_Infrastructure_Reseaux_Securite.pdf",
        "paras": [
            "Je candidate au poste d'Ingénieur Infrastructure, Réseaux et Sécurité au sein de "
            "[ENTREPRISE]. Ingénieur diplômé de l'École Nationale Supérieure Polytechnique de Yaoundé, "
            "je déploie et j'exploite depuis plus de 3 ans des infrastructures multi sites, en MSP "
            "international et en banque, avec la sécurité intégrée à chaque couche.",
            "Chez GOTECH Madagascar : switching et routage OSPF et BGP, SD-WAN et liens télécom, "
            "pare-feux NGFW FortiGate, Checkpoint, Huawei et Cisco Firepower, Windows Server, Active "
            "Directory, Linux, VMware, Proxmox et SAN, sauvegarde NAKIVO, Veeam et LTO, supervision "
            "Zabbix, Grafana et Prometheus, contribution aux PCA et PRA. Chez ENIX SARL, audits "
            "techniques et recommandations. Mon stage à la Société Générale Cameroun m'a donné les "
            "réflexes de continuité du secteur bancaire.",
            "Pour [ENTREPRISE], je m'engage sur la fiabilité et l'évolution de vos plateformes : "
            "exploitation propre, optimisation des architectures, continuité de service, une "
            "documentation honnête grâce à OpsDoc et une supervision lisible grâce à OpsInsight, mes "
            "projets publics sur DailyOps.Tech.",
            CLOSING,
        ],
    },
    "informaticien": {
        "poste": "Ingénieur Systèmes, Réseaux et Support IT",
        "objet": "Candidature au poste d'Ingénieur Systèmes, Réseaux et Support IT",
        "fichier": "LM_STEVE_BA-NDOUWE_Ingenieur_Systemes_Reseaux_Support_IT.pdf",
        "paras": [
            "Je candidate au poste d'Ingénieur Systèmes, Réseaux et Support IT au sein de [ENTREPRISE]. "
            "Ingénieur diplômé de l'École Nationale Supérieure Polytechnique de Yaoundé, j'interviens "
            "depuis plus de 3 ans du poste de travail au serveur, en MSP international et en banque. "
            "Polyvalent, autonome et rigoureux.",
            "Chez GOTECH Madagascar : support utilisateurs N1 à N3, administration Windows Server, "
            "Active Directory, Microsoft 365 et messagerie, réseaux switches, Wi-Fi, VLAN et VPN, "
            "scripts PowerShell et Python, sauvegardes NAKIVO et Veeam, supervision Zabbix et Grafana. "
            "Chez ENIX SARL, analyses de risques et support aux clients. Mon stage à la Société "
            "Générale Cameroun m'a formé aux environnements critiques.",
            "Pour [ENTREPRISE], je propose un profil complet : fiabiliser l'existant, automatiser les "
            "tâches répétitives, sécuriser les accès et les données, et documenter pour que l'équipe "
            "monte en compétence. OpsDoc, ma documentation versionnée publiée sur DailyOps.Tech, "
            "illustre cette approche.",
            CLOSING,
        ],
    },
}

DESTINATAIRE_DEFAUT = ["[ENTREPRISE]", "[ADRESSE]", "[VILLE]", "À l'attention du Service Recrutement"]


def build_lm(key, entreprise=None, destinataire=None, objet=None, paras=None, fichier=None):
    """Génère la lettre du profil. Passer entreprise=... remplace [ENTREPRISE], [ADRESSE] reste à adapter."""
    d = LM_DATA[key]
    paras = list(paras if paras is not None else d["paras"])
    destinataire = list(destinataire if destinataire is not None else DESTINATAIRE_DEFAUT)
    objet = objet if objet is not None else d["objet"]
    if entreprise:
        paras = [p.replace("[ENTREPRISE]", entreprise) for p in paras]
        destinataire = [l.replace("[ENTREPRISE]", entreprise) for l in destinataire]
        objet = objet.replace("[ENTREPRISE]", entreprise)

    pdf = FPDF("P", "mm", "A4")
    fonts(pdf)
    pdf.set_auto_page_break(True, margin=15)
    pdf.set_margins(ML, 15, 15)
    pdf.set_title(f"Lettre de motivation Steve BA-NDOUWE, {d['poste']}")
    pdf.set_author("Steve BA-NDOUWE")
    pdf.add_page()

    # ---- bandeau identité : nom d'abord (identification immédiate), titre cible en dessous
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, 210, 26, style="F")
    pdf.set_fill_color(*TURQ)
    pdf.rect(0, 26, 210, 1.2, style="F")
    pdf.set_xy(ML, 4.5)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("AU", "B", 11.5)
    pdf.cell(LARG, 5, "STEVE BA-NDOUWE")
    pdf.set_xy(ML, 10.8)
    pdf.set_text_color(*TURQ)
    pdf.set_font("AU", "B", 10)
    pdf.cell(LARG, 4.6, d["poste"])
    pdf.set_xy(ML, 17.2)
    pdf.set_font("AU", "", 7.8)
    pdf.set_text_color(180, 195, 210)
    pdf.write(4.5, "+237 654 489 649  |  ")
    pdf.set_text_color(*TURQ)
    pdf.write(4.5, "steve.ba-ndouwe@dailyops.tech", link="mailto:steve.ba-ndouwe@dailyops.tech")
    pdf.set_text_color(180, 195, 210)
    pdf.write(4.5, "  |  Yaoundé, Cameroun  |  ")
    pdf.set_text_color(*TURQ)
    pdf.write(4.5, "dailyops.tech", link="https://dailyops.tech")

    # ---- destinataire à droite
    y = 33
    pdf.set_xy(XD, y)
    pdf.set_text_color(*NAVY)
    pdf.set_font("AU", "B", 9.5)
    pdf.cell(WD, 4.8, destinataire[0])
    pdf.set_font("AU", "", 9)
    pdf.set_text_color(*INK)
    for lig in destinataire[1:]:
        if lig.startswith("À l'attention"):
            y += 6
        y += 4.6
        pdf.set_xy(XD, y)
        pdf.cell(WD, 4.6, lig)

    # ---- lieu et date à droite, en toutes lettres
    y += 10
    pdf.set_xy(XD, y)
    pdf.set_font("AU", "", 9.5)
    pdf.set_text_color(*INK)
    j = datetime.date.today()
    pdf.cell(WD, 4.8, f"Yaoundé, le {j.day} {MOIS[j.month - 1]} {j.year}")

    # ---- objet à gauche, gras, filet turquoise
    y += 9
    pdf.set_xy(ML, y)
    pdf.set_text_color(*NAVY)
    pdf.set_font("AU", "B", 10.5)
    pdf.multi_cell(WO, 5.5, f"Objet : {objet}", align="L")
    y = pdf.get_y() + 1.5
    pdf.set_draw_color(*TURQ)
    pdf.set_line_width(0.5)
    pdf.line(ML, y, ML + 42, y)
    pdf.set_line_width(0.2)

    # ---- salutation
    y += 7
    pdf.set_xy(ML, y)
    pdf.set_text_color(*INK)
    pdf.set_font("AU", "B", 10)
    pdf.cell(LARG, 5.5, "Madame, Monsieur,")
    y += 9

    # ---- corps justifié
    pdf.set_font("AU", "", 10)
    pdf.set_text_color(*INK)
    for para in paras:
        pdf.set_xy(ML, y)
        pdf.multi_cell(LARG, 5.5, para, align="J")
        y = pdf.get_y() + 3.5

    # ---- signature à droite (place pour le paraphe) puis pièce jointe
    y += 10
    pdf.set_xy(XD, y)
    pdf.set_text_color(*NAVY)
    pdf.set_font("AU", "B", 10.5)
    pdf.cell(WD, 5.5, "Steve BA-NDOUWE")
    y += 24
    pdf.set_xy(ML, y)
    pdf.set_text_color(*GRAY)
    pdf.set_font("AU", "I", 8)
    pdf.cell(LARG, 4, "PJ : CV")

    out = os.path.join(OUT, fichier or d["fichier"])
    pdf.output(out)
    return out


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for k in ["support", "securite", "infrastructure", "informaticien"]:
        print(k, "->", build_lm(k))
