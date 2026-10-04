# OrientSkill AI — Plateforme d'intelligence professionnelle pour les jeunes Camerounais

> **De l'orientation à l'opportunité, l'IA accompagne chaque jeune dans son parcours professionnel.**

Implémentation du MVP défini dans le cahier des charges
[`projet_ia_minjec_formalisation-1.md`](./projet_ia_minjec_formalisation-1.md) (§55 — modules 1 à 10).
Projet initié dans le cadre du MINJEC.

## Philosophie

```text
Se connaître → Comprendre ses compétences → Comprendre le marché
→ Choisir une direction → Acquérir les bonnes compétences
→ Trouver les opportunités → Adapter sa candidature → Candidater
```

Le système transforme la donnée en action, sans jamais inventer : le CV ciblé
et la lettre de motivation n'utilisent **que** les informations du profil
validé par le jeune (§47 — gouvernance de l'IA).

## Structure du projet

```text
SkillJob/
├── projet_ia_minjec_formalisation-1.md   Cahier des charges (référentiel maître)
├── docs/
│   └── API_CONTRACT.md                   Contrat d'API strict (backend ↔ frontend)
├── backend/                              API FastAPI + moteurs IA
│   ├── app/
│   │   ├── api/                          Routes : auth, profile, questionnaire, skills,
│   │   │                                 careers, jobs, applications, documents,
│   │   │                                 dashboard, market, learning, assistant
│   │   ├── services/                     Moteurs : extraction CV, questionnaire,
│   │   │                                 matching explicable, orientation, générateur
│   │   │                                 CV/lettre, marché, learning, assistant
│   │   ├── models.py, schemas.py         Données (User, Profile, Skill, Job, Match…)
│   │   └── security.py                   JWT + PBKDF2
│   ├── data/                             Base locale maîtrisée (démo concours) :
│   │                                     81 compétences, 13 métiers, 22 offres CM,
│   │                                     ressources de formation
│   └── tests/                            16 tests API (pytest)
└── frontend/                             Interface React + Vite (mobile-first)
    └── src/pages/                        Dashboard, Inbox, Opportunités, Matching,
                                          Candidatures, Carrière, Compétences,
                                          Learning, Documents, Profil, Assistant,
                                          Onboarding (CV / questionnaire)
```

## Lancement rapide

### 1. Backend (port 8000)

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows (bash) — .venv\Scripts\activate sous cmd
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000 --reload
```

- Base SQLite créée et alimentée automatiquement au premier démarrage
  (compétences, métiers, 22 offres, ressources, programmes publics,
  entrepreneuriat, utilisateurs démo).
- Comptes de démonstration :
  - **Candidat** : `demo@orientskill.cm / demo1234` (profil IT réseau, 2 candidatures)
  - **Recruteur** : `recruteur@orientskill.cm / recruteur1234` (entreprise « Numérik Services CM »)
  - **Administrateur** : `admin@orientskill.cm / admin1234` (console admin)

### 2. Frontend (port 5173)

```bash
cd frontend
npm install
npm run dev
```

Ouvrir http://localhost:5173 — le proxy Vite relaie `/api` vers le backend.

## Ce qui fonctionne réellement (MVP démontrable)

| Module (§55) | Implémentation |
|---|---|
| 1. Diagnostic | Import CV (texte collé, PDF, TXT) **et** questionnaire intelligent — brouillon jamais enregistré sans validation humaine |
| 2. Profil intelligent | Extraction formation / expériences (formelles **et informelles**) / compétences / certifications / langues, normalisation alias FR-EN |
| 3. Orientation | Métiers compatibles avec score, accessibilité (immédiat / après montée en compétences), actions recommandées |
| 4. Base d'opportunités | 22 offres camerounaises sourcées (source, URL, dates de publication/collecte) |
| 5. Matching | Score 0-100 **explicable** : couvertes ✓ / partielles △ / manquantes ○, forces, explication en français, actions |
| 6. Gap Analysis | Écarts agrégés sur toutes les offres, compétences prioritaires |
| 7. CV ciblé | CV markdown adapté à l'offre + lettre de motivation + préparation d'entretien — zéro invention |
| 8. Dashboard | Poste de pilotage (§27) : nouvelles opportunités, correspondances fortes, prochaine action, tendances |
| 9. Assistant | Conversation ancrée sur les données réelles ; **suggestions dynamiques** calculées depuis l'état réel du profil et du marché ; LLM optionnel configurable sans toucher au code |
| 10. Démonstration marché | Tendances par compétence/secteur calculées sur la base d'offres, mini-ATS candidatures, inbox |

## Console d'administration (V1.1)

Accessible aux comptes de rôle `admin` (`admin@orientskill.cm / admin1234`), sans toucher au code :

- **Vue générale** : statistiques plateforme (utilisateurs, profils, offres, candidatures, documents) et état des services.
- **Paramètres** : SMTP (notifications e-mail, test de connexion réel), moteur LLM (fournisseur OpenAI-compatible, modèle, URL, clé — test de connexion), agrégateurs Telegram/WhatsApp (identifiants stockés pour l'activation V2). Les secrets ne sont jamais renvoyés par l'API ; un champ laissé vide conserve la valeur existante.
- **Connecteurs** : catalogue formalisé qui distingue ce qui est opérationnel, à configurer, et ce qui relève de la roadmap V2/V3 (LinkedIn via mécanismes autorisés, collecte multi-source, Skill Graph national, vérification de credentials). Détails : `docs/ROADMAP_V2_V3.md`.
- **Base d'offres** : CRUD complet sur la base locale (compétences requises essentielles/appréciées, source + URL obligatoires).

## Export PDF professionnel

Les CV et lettres de motivation s'exportent en **PDF A4 mis en page** (reportlab) :
CV aux normes internationales (en-tête, compétences ciblées d'abord, expériences datées,
formation, certifications), lettre aux conventions épistolaires françaises
(expéditeur/destinataire, objet, formule de politesse). Le contenu provient
exclusivement du profil validé (§47). Trois **modèles au choix** :
Classique, **ATS** (compatible robots de tri), Moderne.

## Sécurité (V1.2)

- **MFA TOTP** pour tous les comptes (Google Authenticator, Authy…) : QR code,
  codes de récupération à usage unique, désactivation par code.
- **Réinitialisation MFA par l'administrateur** pour les cas extrêmes
  (perte de l'app ET des codes).
- **Genre enregistré à l'inscription** : plus de « (se) » dans les documents,
  la lettre s'accorde automatiquement.
- **Vérification de profil à notre manière** : dépôt de pièce d'identité
  (CNI/passeport), examen par un administrateur, badge « Profil vérifié »
  visible des recruteurs et intégré aux CV.

## Ancrage camerounais (V1.3)

- **Localisation structurée** : 10 régions → 57 départements → arrondissements →
  ville, en listes en cascade à l'inscription et dans le profil.
- **Formation inclusive** : CEP, FSLC, GCE O/A Level, diplôme d'ingénieur,
  recyclages et compétences de terrain (chauffeurs, plombiers, manœuvres,
  gardiens vigiles) — l'absence de diplôme n'est jamais éliminatoire.
- **Programmes publics** : offres du FNE, bourses MINFOP, accompagnements
  MINJEC et MINPME.
- **Espace entrepreneuriat** (§11bis) : concours, appels à projets,
  accompagnements, financements et préparation bancaire documentée
  (exigences réelles des banques).

## Espace recruteur (V1.3 → V2)

- Inscription par type : **Entreprise / Cabinet RH** (aucun champ personnel,
  le compte EST la structure) ou **Recruteur indépendant** (inscription complète).
- Publication d'offres avec branding, y compris **« Générer depuis une
  description »** (l'IA structure la phrase du recruteur) et **import par URL
  (LinkedIn / JSON-LD)** — toujours validés par un humain.
- **Talent search** par compétences, métier, région, secteur, avec matching
  explicable. **Shortlists** de candidats privées par entreprise.
- **Statut partagé des candidatures** : le recruteur fait avancer le pipeline
  visible côté candidat (timeline journalisée + notification).
- **Carte de profil** : le recruteur voit uniquement la carte du talent
  (jamais ses coordonnées) et le contacte via la **messagerie interne**
  (identité complète de l'entreprise visible du candidat).

## V2 — Collecte multi-source & canaux (implémenté)

- **Ingestion multi-source** (§50) : connecteurs RSS et API JSON,
  normalisation, **déduplication inter-sources**, scoring de fiabilité par
  source — console admin « Sources & collecte » avec exécution manuelle.
- **Import d'offre par URL** (LinkedIn ou autre) via le balisage public
  JSON-LD : mécanisme léger et autorisé, une page à la fois, brouillon à valider.
- **Bot Telegram** (§25bis) : consultation conversationnelle des offres
  (/offres, /offres comptable…), démarré automatiquement quand l'admin
  active le canal (Bot API officielle, long polling).
- **Notifications intelligentes** (§52) : digest quotidien des nouvelles
  offres correspondant au profil (score ≥ 45), filtrage anti-surcharge,
  planificateur intégré activable dans la console admin.
- **Projets & portfolio** : réalisations avec liens de preuve, valorisées
  dans le matching et le parcours « absence d'information ≠ absence de
  compétence » (§48).

## V3 — Intelligence institutionnelle (implémenté)

- **Dashboard institutionnel** (§39) : agrégats anonymisés — offre vs
  demande de compétences, **écarts avec ratio de tension** (priorités de
  formation), répartition géographique, secteurs, candidatures par étape.
- **Skill Graph** (§41) : exploration du graphe compétence ↔ métiers ↔
  offres ↔ talents ↔ formations, avec compétences voisines qui dessinent
  des trajectoires professionnelles.
- **Vérification de profil renforcée** : dépôt en deux temps (aperçu puis
  confirmation), comparaison profil ↔ pièce côté admin, **refus motivé**
  communiqué au candidat.
- **Gestion des contenus publics** : CRUD complet des Programmes publics
  (FNE, MINFOP, MINPME, concours) et des ressources Entrepreneuriat.

## Organisation de l'interface

- **Sidebar talent regroupée** : Accueil · Opportunités · Mon parcours ·
  Compte — hiérarchie claire au lieu d'une liste plate (§78).
- **Paramètres séparés du Profil** : MFA, notifications et vérification de
  profil vivent dans « Paramètres » (tous rôles) ; la page Profil reste
  dédiée au profil professionnel.
- **Carte talent côté recruteur** : avatar initiales, badge de vérification,
  résumé, match explicable, compétences et actions — présentation soignée.

## Ce qui est volontairement simulé / roadmap (V2-V3)

Connecteurs LinkedIn et collecte multi-source automatisée, espace recruteur
complet, WhatsApp/Telegram, Skill Graph national, vérification de credentials,
données institutionnelles à grande échelle — voir §56-57 et §76 du cahier des charges.

## Configuration optionnelle

Le moteur LLM se configure depuis la console admin (Paramètres). Les
variables d'environnement restent un repli :

```bash
# backend/.env ou variables d'environnement
LLM_PROVIDER=openai          # active le LLM pour l'assistant (sinon : règles locales)
LLM_API_KEY=...
LLM_BASE_URL=...             # tout endpoint compatible OpenAI
LLM_MODEL=...
```

## Tests

```bash
cd backend
source .venv/Scripts/activate
python -m pytest tests -q    # 16 tests : auth, import CV, matching, CV ciblé,
                             # anti-invention, candidatures, dashboard, assistant…
```

```bash
cd frontend
npm run build                # build de production Vite
```

## Principes non négociables (cahier des charges)

- **Pas d'invention** (§47) : aucun diplôme, expérience ou compétence inventé.
- **Explicabilité** (§12) : jamais un score opaque ; toujours forces, écarts et actions.
- **Validation humaine** : le jeune valide son profil avant tout enregistrement.
- **Traçabilité** (§51) : chaque offre conserve source, URL et dates.
- **Parcours camerounais** (§5 bis) : les expériences informelles comptent ;
  « absence d'information ≠ absence de compétence » (§48).
