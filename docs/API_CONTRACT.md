# Contrat d'API : OrientSkill AI (MVP)

Backend : FastAPI, préfixe `/api`, base locale `http://localhost:8110`.
Frontend : React + Vite (proxy `/api` → `localhost:8110`), port `5190`.
Auth : JWT dans l'en-tête `Authorization: Bearer <token>` (stocké en `localStorage` côté frontend, clé `orientskill_token`).
Format : JSON UTF-8. Toutes les listes supportent la pagination simple `?skip=&limit=` (défaut limit=50).

## 1. Auth

### POST /api/auth/register
Body : `{ "email": string, "password": string, "full_name": string, "phone"?: string }`
→ `201 { "token": string, "user": User }`
L'inscription candidat est volontairement minimale : genre et localisation
sont facultatifs et se complètent ensuite dans le profil.

### POST /api/auth/login
Body : `{ "email": string, "password": string }`
→ `{ "token": string, "user": User }`

### GET /api/auth/me → `User`

```text
User { id, email, full_name, role: "candidate"|"recruiter"|"admin", phone?, created_at }
```

## 2. Profil (Profile Engine)

### GET /api/profile → `Profile | null`

```text
Profile {
  user_id, summary, title?, location?, mobility?, availability?,
  education:     [{ id, degree, institution, field, start_year, end_year? }],
  experiences:   [{ id, title, organization, type: "formal"|"informal"|"freelance"|"volunteer"|"apprenticeship"|"project",
                    description, start_date?, end_date?, skills: string[] }],
  certifications:[{ id, name, issuer, year }],
  languages:     [{ id, language, level }],
  projects:      [{ id, name, description, skills: string[] }],
  skills:        [{ skill: string, category: string, proficiency: "debutant"|"intermediaire"|"avance",
                    source: "declared"|"inferred"|"evidence", evidence_count: int }],
  preferences:   { domain_id: int|null, specialty_ids: int[], domain_other: string,
                   sectors: string[], target_roles: string[], contract_types: string[], remote_ok: bool }
}
```

### PUT /api/profile
Body : `Profile` (complet ou partiel) → `Profile` (profil maître mis à jour)

### GET /api/profile/cv-visibility → `CvVisibility`
### PUT /api/profile/cv-visibility

```text
Body : { visible: bool, document_id?: int }
CvVisibility { visible: bool, document_id: int|null, document: Document|null }
```

Partage **opt-in** d'un seul CV généraliste avec les recruteurs. Le
`document_id` doit appartenir au candidat, être de type `cv` et ne pas être
rattaché à une offre (`job_id = null`) : un CV ciblé reste privé et renvoie
`422`. `visible: false` retire immédiatement l'accès recruteur. La suppression
du CV partagé désactive aussi le partage.

### POST /api/profile/import-cv
Accepte soit JSON `{ "text": "contenu du CV" }`, soit `multipart/form-data` avec un fichier `.pdf` ou `.txt` (champ `file`).
→ `{ "draft": Profile, "report": { skills_found: int, experiences_found: int, certifications_found: int, degrees_found: int, career_fields: string[] } }`

Le brouillon **n'est pas enregistré** : l'utilisateur valide via `PUT /api/profile` (principe "validation humaine", §47).

### POST /api/profile/import-cv/library

Body : `{ "document_id": int }`. Réimporte un CV de la bibliothèque du candidat
(CV généraliste ou ciblé) sous forme de brouillon, au même format que
`POST /api/profile/import-cv`. Le document doit appartenir au candidat
(`404` sinon) et être de type `cv` (`422` pour une lettre). Le profil maître
n'est jamais modifié : la validation reste humaine.

Les CV générés conservent un instantané interne du profil validé qui les a
produits. Lorsqu'il existe, l'import le restitue sans réinterpréter la mise
en page. Les anciens documents sans instantané sont relus section par section
depuis le markdown structuré de `cv_builder` (titres, dates, niveaux et
compétences tels quels). Un document non reconnaissable renvoie `422` plutôt
que de produire un profil approximatif.

### GET /api/questionnaire → `{ steps: [ { id, title, questions: [{ id, label, type: "text"|"textarea"|"multi_choice"|"choice"|"list", options?: string[] }] } ] }`

### POST /api/questionnaire/submit
Body : `{ "answers": { "<question_id>": any } }` → `{ "draft": Profile, "report": {...} }` (même format que l'import CV)

## 3. Compétences

### GET /api/skills/taxonomy → `[{ name, category, aliases: string[] }]`
### GET /api/skills/market → `[{ name, demand_count, trend: "up"|"stable"|"down", pct_change: int }]` (tendances issues des offres)

## 4. Carrières / Orientation (Career + Orientation Intelligence)

### GET /api/careers
→ `[{ id, title, family, description, required_skills: [{ name, importance: "core"|"preferred" }],
      match: { score: 0-100, level: "forte"|"moyenne"|"faible",
               covered: string[], partial: string[], missing: string[], strengths: string[],
               accessibility: "immediate"|"with_upskilling"|"long_term",
               recommended_actions: string[], explanation: string } }]` (trié par score décroissant)

Score explicable (§12), mêmes règles que le matching d'offres : ✓ couverte,
△ partielle (niveau débutant), ○ manquante. `explanation` en donne la lecture
en français et `accessibility` l'horizon d'accès réel au métier.

## 5. Offres (Job Intelligence) + Matching

### GET /api/jobs?search=&sector=&domain_id=&specialty_id=&location=&contract_type=&min_score=

Filtres du référentiel : `domain_id` (domaine principal) et `specialty_id`
(spécialité précise) s'ajoutent aux filtres texte historiques.

→ `[{ id, title, company, location, sector, contract_type: "CDI"|"CDD"|"Stage"|"Freelance"|"Apprentissage",
      published_at, deadline: datetime | null, source: { name, url }, match_score: 0-100 | null,
      photo_url: string | null,
      domain_id: int|null, domain_name: string|null,
      specialty_id: int|null, specialty_name: string|null,
      required_skills: [{ name, importance: "core"|"preferred", level?: string }] }]`

### GET /api/jobs/{id} → `{ job: Job, match: Match | null, my_report: JobReport | null }`

```text
Job { id, title, company, location, sector, contract_type, description, requirements: string,
      photo_url: string | null,
      domain_id: int|null, domain_name: string|null,
      specialty_id: int|null, specialty_name: string|null,
      required_skills: [{ name, importance: "core"|"preferred", level?: string }],
      published_at, deadline?, source: { name, url }, }

Match {
  score: 0-100, level: "forte"|"moyenne"|"faible",
  covered: string[], partial: string[], missing: string[],
  strengths: string[], explanation: string, recommended_actions: string[]
}
```

Le score est **explicable** (§12) : jamais un simple pourcentage opaque.

`photo_url` = photo d'illustration **facultative** déposée par le publieur
(recruteur ou administration) ; `null` = offre sans visuel.
`GET /api/jobs/{id}/photo` sert le fichier (404 si aucune photo).

`my_report` (connecté) : dernier signalement du candidat sur cette offre,
`null` s'il n'en a pas déposé (voir § 5bis).

## 5bis. Signalements d'offres

Le candidat signale une offre problématique (arnaque, contenu trompeur,
offre expirée, discrimination, doublon, autre). Le signalement est
persistant : il est traité dans la console d'administration et le candidat
suit son statut depuis la fiche de l'offre.

### POST /api/jobs/{id}/reports → 201 `JobReport`

Body : `{ "reason": "arnaque"|"contenu_trompeur"|"offre_expiree"|"discrimination"|"doublon"|"autre",
          "details": string }`

```text
JobReport { id, job_id, reason, details, status: "nouveau"|"en_cours"|"traite"|"rejete",
            admin_note, created_at, updated_at, job_title, company }
```

- Motif invalide → 422 ; `details` ≤ 2000 caractères.
- Motif `autre` : `details` obligatoire (≥ 10 caractères) → 422 sinon.
- Un seul signalement OUVERT par candidat et par offre : un second appel
  renvoie **409** (« Vous avez déjà signalé cette offre »).

### Côté administration (rôle `admin`)

- `GET /api/admin/reports?status=nouveau|en_cours|traite|rejete`
  → `[JobReportAdmin]` : `{ ...JobReport, user_id, user_name, user_email }`,
  trié du plus récent, limité à 300.
- `PUT /api/admin/reports/{id}` `{ "status", "admin_note" }` → `JobReportAdmin` :
  enregistre la décision et la note (visible du candidat sur la fiche de
  l'offre). Statut invalide → 422, signalement introuvable → 404.

## 5ter. Référentiel des domaines et spécialités

Arbre publique (tous rôles connectés) : le candidat choisit son domaine et
ses spécialités dans son profil, le recruteur précise le domaine recherché
dans ses filtres, l'administration maintient le référentiel.

### GET /api/domains → `[Domain]`

```text
Domain { id, slug, name, description, aliases: string[], sort_order, active,
         specialties: [{ id, slug, name, description, aliases, sort_order, active }] }
```

- Seed initial : `backend/data/domains.json` (25 domaines, 291 spécialités),
  dont « Secteur informel » (§5bis) et « Autres ». Les spécialités IT
  granulaires (Administration systèmes, Réseaux et télécommunications,
  Intelligence artificielle, Data science, Ingénierie des données, Génie
  logiciel, Analyse programme) sont resynchronisées au démarrage si
  absentes : le référentiel s'enrichit sans écraser les corrections admin.
- Désactivation **logique** uniquement : un domaine retiré n'apparaît plus
  dans l'arbre publique mais reste dans les profils et offres qui le citent
  (jamais de suppression physique destructrice).

### Gestion (admin, console « Domaines & spécialités »)

- `GET /api/admin/domains` : arbre complet, y compris inactifs.
- `POST /api/admin/domains` `{ name, description?, aliases? }` → 201 `Domain`.
- `PUT /api/admin/domains/{id}` (correction du libellé/description).
- `DELETE /api/admin/domains/{id}` : **désactivation** (active = false).
- `POST /api/admin/domains/{id}/specialties` `{ name, description?, aliases? }` → 201.
- `PUT /api/admin/domains/{id}/specialties/{specialty_id}`,
  `DELETE /api/admin/domains/{id}/specialties/{specialty_id}` (désactivation).

## 6. Candidatures (mini-ATS personnel + soumission réelle)

### GET /api/applications → `[ Application ]`
### POST /api/applications `{ "job_id": int }` → `Application` (suivi simple)
### POST /api/applications/jobs/{job_id}/submit → `Application` (SOUMISSION RÉELLE)

Body de la soumission :

```text
{ "cv_document_id": int,          // OBLIGATOIRE : CV de la bibliothèque du candidat
  "cover_letter_document_id": int?,  // FACULTATIF
  "cover_note": string }             // message au recruteur, 2000 caractères max
```

La soumission détermine automatiquement le canal :

- **`platform`** : l'offre est publiée par un recruteur OrientSkill AI
  (compte rattaché). Les documents sont transmis au recruteur via la
  messagerie interne ; sa réponse part directement au candidat et reste
  tracée dans l'historique.
- **`external`** : l'offre vient d'une source externe.
  - Si l'offre a une adresse de candidature (`apply_email`) et que le
    SMTP administrateur est configuré : OrientSkill AI **transmet
    elle-même la candidature par e-mail** au publieur (CV + lettre en
    PDF joints, `Reply-To` adressé au candidat pour que la réponse lui
    parvienne directement). La timeline note
    « Candidature transmise automatiquement par e-mail à … ».
  - Sinon (pas d'adresse ou SMTP non configuré) : l'envoi est
    horodaté côté plateforme, la timeline note
    « transmission automatique non effectuée », et le candidat suit
    les instructions du publieur (`apply_url`, `apply_instructions`).

Réponses : `400` si déjà envoyée, `422` si le CV/lettre n'appartient pas
au candidat ou n'est pas du bon type.

```text
Application { id, user_id, job_id, job: JobSummary,
  status: "identifiee"|"cv_prepare"|"envoyee"|"en_attente"|"entretien"|"offre"|"acceptee"|"refusee"|"retiree"|"declinee",
  timeline: [{ at, event, by?, reason? }],
  documents: [{ id, kind: "cv"|"cover_letter", title }],
  apply_channel: "platform"|"external"|"email"|"",
  submitted_at: datetime | null,
  cover_note: string,
  apply_instructions: string, apply_email: string, apply_url: string }
```

`email` : candidature reçue sur la boîte interne puis transmise à
l'entreprise (voir §6ter). Les pièces d'origine restent attachées à
l'e-mail de transmission ; le profil n'est jamais complété d'office.

### PATCH /api/applications/{id} `{ "status": ..., "reason"?: string }` → `Application`

Action du candidat uniquement. Transitions autorisées :
`identifiee` → `cv_prepare`|`envoyee`|`retiree` ; `cv_prepare` →
`envoyee`|`retiree` ; `envoyee`|`en_attente`|`entretien` → `retiree` ;
`offre` → `acceptee`|`declinee`|`retiree`. Toute autre transition est
refusée en `403` avec un message actionnable. Un statut inconnu reste
`422`. Le motif éventuel est conservé dans l'historique.

Les `event` de l'historique sont écrits par le backend
(`app/services/applications.py`, dictionnaire `STATUS_LABELS`) : c'est la
source unique des libellés d'étape, réutilisée par l'assistant pour parler
du suivi réel du candidat (aucune étape n'est inventée). `by` identifie
l'auteur de la transition (candidat, entreprise, admin) et `reason` le
motif éventuel.

### Suivi admin : GET /api/admin/applications?status=&channel=&limit=

Toutes les candidatures de la plateforme (tous candidats confondus) :
`[{ id, candidate_name, candidate_email, candidate_photo_url,
job_title, job_company, job_id, status, apply_channel, apply_url,
apply_email, apply_instructions, submitted_at, cover_note,
document_count, timeline }]`.
L'admin voit qui a postulé où, par quel canal, avec combien de
documents, et retrouve le lien de postulation externe (site ou e-mail
du publieur). Le canal `email` correspond aux candidatures reçues par la
boîte interne puis transmises à l'entreprise. Photo :
`GET /api/admin/users/{id}/photo` (rôle admin).

### PATCH /api/admin/applications/{id} `{ "status": ..., "reason": ... }` → `{ ok, status, previous }`

Arbitrage admin : toute transition est autorisée, y compris la
réouverture d'un statut terminal, mais `reason` est obligatoire
(3 caractères minimum). L'événement est ajouté à la timeline avec
l'auteur admin, la date et le motif ; le candidat est notifié. Même
statut ou statut inconnu : `422`. Candidature introuvable : `404`.

Le journal détaillé des messages entrants (routage, transmission, accès,
pièces jointes) est exposé par `GET /api/admin/inbound-emails` et
`POST /api/admin/inbound-emails/{id}/resend-access` (voir §12).

## 6bis. Candidature publique depuis le lien d'une offre

Aucune authentification : le recruteur partage
`{PUBLIC_BASE_URL}/postuler/{job_id}`.

- `GET /api/public/jobs/{job_id}` → fiche publique de l'offre :
  identité du poste et de l'entreprise, description, compétences
  demandées, échéance, source et `apply_channel`. Aucune donnée
  personnelle n'est exposée. Champs ajoutés pour la candidature par
  e-mail : `email_apply_address` (adresse interne), `email_reference`
  (`OS-XXXX`) et `poster_url`.
- `GET /api/public/jobs/{job_id}/poster.svg` → visuel 1200 x 1500
  (`image/svg+xml`), généré depuis l'offre et l'adresse interne. `503`
  tant que `inbound.address` n'est pas configurée. Aucune ressource
  externe, aucun script.
- `POST /api/public/jobs/{job_id}/apply`
  Body : `{ "full_name": string, "email": string, "phone": string, "motivation"?: string }`
  → `201 { token, user: User, application_id, email_sent }`.

Le compte candidat est créé automatiquement (mot de passe provisoire
aléatoire, téléphone conservé en privé), la candidature est enregistrée
comme envoyée sur le canal `platform`, et les accès sont envoyés par
e-mail. La session est renvoyée immédiatement : le candidat peut
compléter son profil sans attendre. `400` si l'offre est fermée ou se
postule en externe, `409` si un compte existe déjà avec cet e-mail
(le message invite à se connecter).

## 6ter. Candidatures reçues par e-mail (boîte interne)

Deux entrées, configurées par l'admin (§12) :

- relève IMAP périodique de la boîte interne ;
- webhook signé, pour un fournisseur qui pousse les messages.

### POST /api/public/inbound-email

Body normalisé :

```text
{ sender | from: string, sender_name?, subject?, text?, html?,
  message_id?, attachments?: [{ filename, content_type?, content_base64 }] }
```

La signature est vérifiée : `X-OrientSkill-Secret`, `X-Webhook-Secret`,
`Authorization: Bearer <secret>` ou `?secret=`. `401` si elle est fausse,
`503` si aucun secret n'est configuré. Le message est idempotent grâce à
`message_id`.

Routage, dans cet ordre : référence `OS-XXXX` (objet ou corps), mots-clés
`apply_keywords` de l'offre, puis titre ou entreprise. En cas
d'ambiguïté, le message est marqué `non_routee` et conservé pour revue :
il n'est jamais transmis à une mauvaise entreprise. Quand une offre est
identifiée :

1. la candidature est créée ou complétée avec `apply_channel = "email"` ;
2. un compte candidat est créé si l'expéditeur n'en a pas, et ses accès
   lui sont envoyés ;
3. le message, le corps et les pièces jointes d'origine sont transmis à
   l'adresse RH de l'offre (ou à l'adresse de secours), avec `Reply-To`
   vers le candidat.

Réponse : `{ ok, duplicate, status: "transmise"|"recue"|"non_routee",
inbound_id, job_id?, application_id?, user_id?, account_created,
access_email_sent, forward_email_sent, routing, detail }`.

## 7. Documents (CV Intelligence + Application Assistant)

### POST /api/jobs/{id}/cv → `Document` (CV ciblé, génération règles/templating, **sans invention**)

Body : `{ "template": "classique", "accent": "vert" }` (les deux facultatifs).

```text
Modèles de CV (template) :
  classique      sobre, une colonne, compétences ciblées en tête
  ats            noir et blanc, intitulés standards, mono-colonne (robots)
  moderne        bandeau marine + accent, pastilles de compétences
  deux_colonnes  bandeau marine + panneau latéral clair (compétences,
                 langues) et colonne parcours
  elegant        serif, liserés fins, pour les administrations, banques, éducation
  compact        marges resserrées, tout sur une page

Couleurs d'accent (accent) :
  vert | bleu | orange | bordeaux | ardoise | violet | turquoise | rouge |
  rose | indigo | ambre | menthe | brun, ou une couleur libre "#RRGGBB"
  (stockée sur le document, réutilisée à l'export). Le modèle ATS garde
  sa charte bleu nuit / turquoise tant qu'aucune couleur n'est choisie,
  mais honore une couleur explicite. Inconnue -> 422.
```

### POST /api/cv → `Document` (CV **GÉNÉRALISTE**, sans offre ciblée)

Body : `{ "template", "accent" }` (facultatifs). Le document a `job_id: null` :
compétences triées par preuves, expériences chronologiques, aucune mention
de « poste visé ». 400 si aucun profil validé.

### POST /api/jobs/{id}/cover-letter → `Document`

Body : `{ "template": "classique", "accent": "vert" }` (facultatifs).

### POST /api/letter → `Document` (lettre **GÉNÉRALISTE**, sans offre)

Body : `{ "template", "accent" }` (facultatifs). Le document a
`job_id: null` : le destinataire reste à compléter
(`[Nom de l'entreprise]`, `[Ville]`) : aucune coordonnée inventée (§47).
400 si aucun profil validé.

```text
Modèles de lettre : classique (conventions épistolaires),
                   moderne (en-tête accentué), email (format courriel)
```

### POST /api/documents/{id}/refresh → `Document` (mise à jour)

Body : `{ "template", "accent" }` (facultatifs : par défaut, le document
conserve son modèle et son accent). Le contenu est RÉGÉNÉRÉ depuis le
profil validé au moment de l'appel (même offre s'il est ciblé) ; le titre
est réactualisé (modèle/offre). 400 si le document n'est ni un CV ni une
lettre, ou si le profil n'est pas validé ; 422 modèle inconnu.

### DELETE /api/documents/{id} → 204

Suppression définitive d'un document de l'utilisateur. 404 s'il
n'appartient pas à l'utilisateur. Si ce document était le CV généraliste
partagé, le partage recruteur est automatiquement désactivé.

**Chaîne d'adaptation (§15-17)** : l'assistant (`POST /api/assistant`)
propose les textes (accroche du CV, ouverture et correspondance de la
lettre : réorganisation factuelle du profil, §47) pour l'offre mentionnée
ou la meilleure correspondance ; il rédige aussi le COURRIEL
D'ACCOMPAGNEMENT (objet + corps, prêt à coller) et signale ce qu'il reste
à ajouter si des sections du profil sont vides. Ses actions `generate_cv` /
`generate_letter` renvoient le candidat vers la galerie de modèles de
l'offre (`/opportunites/{id}?galerie=cv|lettre`) ; le document généré
s'ouvre dans `/documents?open={id}`. « généraliste / sans offre » dans la
demande = jamais de ciblage (liens `/documents` et `/documents?lettre=1`).

### POST /api/jobs/{id}/interview-prep → `{ likely_questions: string[], technical: string[], behavioral: string[], pitch: string, prep_tips: string[] }`
### GET /api/documents → `[ Document ]`
### GET /api/documents/{id} → `Document`
### GET /api/documents/{id}/export?format=md|pdf → téléchargement (PDF si `reportlab` dispo, sinon markdown)
### GET /api/cv-templates → `[{ id, name, description, ats_friendly, columns }]`
### GET /api/letter-templates → `[{ id, name, description }]`

```text
Document { id, kind: "cv"|"cover_letter", title, content_markdown: string, job_id?,
           template, accent?, created_at }
```

Un modèle change la mise en page (PDF), jamais les faits : le contenu
reste exclusivement issu du profil validé (§47).

## 8. Dashboard / Inbox / Marché / Learning

### GET /api/dashboard

```text
{ name, new_opportunities: int, strong_matches: int, skills_to_improve: string[],
  ongoing_applications: int, interviews_to_prepare: int,
  market_trends: [{ name, trend, pct_change, count, offers }],
  next_action: { label, type: "adapt_cv"|"learn"|"apply"|"prepare_interview",
                 job_id?: int, skill?: string, href?: string },
  learning_focus: { skill, title, provider, resource_key, href } | null,
  autonomous_prepared: { job_id, job_title, company, score, message } | null }
```

`next_action.href` : lien interne direct (backend) vers l'action
(`/jobs/{id}`, `/learning/{key}`, `/dashboard`), traduit côté frontend par
`mapInternalPath()`. `learning_focus` : première ressource de formation
réelle pour l'écart prioritaire, avec sa clé stable (`resource_key`) et son
lien profond `/learning/{resource_key}` ; `null` si aucune ressource.
`autonomous_prepared` : ce que l'agent vient de préparer automatiquement
en mode autonome ; `null` sinon.

`ai_briefing` : message d'accueil personnalisé de l'agent, affiché sur
l'accueil, la page Mon agent et la page Profil. Il contient des
OBSERVATIONS FACTUELLES : correspondances fortes, délais urgents
(« la candidature se termine dans 2 jours, tout est prêt de mon côté »),
formations recommandées au vu des tendances, infos à ajouter au profil
pour renforcer la visibilité. `ai_label` en est le titre.

### GET /api/notifications → `[{ id, at, kind: "new_job"|"strong_match"|"trend"|"learning"|"application"|"expiring"|"report"|"appeal"|"interview", message, job_id?, unread }]`

Rubrique Notifications, distincte de la messagerie interne : les messages
des recruteurs restent dans `/api/messages`. `unread` est calculé à partir
de `users.notifications_seen_at`. `GET /api/inbox` reste un alias masqué,
sans rupture pour les anciens clients. Les événements in-app ne sont pas
conservés indéfiniment : au-delà de **30 jours**, ils disparaissent du flux.

- `GET /api/notifications/unread-count` → `{ count, seen_at }` (badge de la
  barre supérieure, séparé du badge Messages).
- `POST /api/notifications/seen` → `{ count: 0, seen_at }` : marque comme
  lues les notifications affichées à cet instant.

`expiring` : offre correspondant au profil (score >= 45) dont la date
limite arrive sous 7 jours et non encore postulée. `report` : réponse de
l'administration aux signalements du candidat (traité ou rejeté, avec le
motif et la note) ; la fiche de l'offre, elle, n'affiche plus que
« Offre signalée ».

### GET /api/market/trends

```text
{ top_skills: [{ name, count }], trending_up: string[], trending_down: string[],
  sectors: [{ name, offers: int }], emerging: string[] }
```

### GET /api/learning → voir § 10 (Learning)

## 9. Assistant conversationnel

### POST /api/assistant
Body : `{ "message": string, "history": [{ "role": "user"|"assistant", "content": string }],
"conversation_id"?: number }`
→ `{ "reply": string, "suggestions": string[], "links": [{ label, href }] }`

Sans `conversation_id`, la conversation la plus récente est reprise. Chaque
conversation garde son propre mode d'historique et ses propres messages.

Moteur hybride : réponses par règles ancrées sur les données réelles, suggestions DYNAMIQUES calculées depuis l'état du profil et du marché ; bascule vers un LLM si configuré via l'admin (sinon fallback règles). Jamais de données inventées.

Le contexte transmis à l'agent couvre toute la chaîne : identité de
l'utilisateur (nom complet), profil détaillé (résumé, expériences,
formation, certifications, compétences), candidatures, documents déjà
générés (il ne propose pas de refaire ce qui existe), formations suivies,
ressources d'apprentissage avec liens profonds `/learning/{key}`, métiers
recommandés et prochaine action prioritaire. Les liens `href` sont des
chemins internes backend (`/jobs/3`, `/learning/{key}`, `/documents`,
`/applications`) traduits par `mapInternalPath()` côté frontend.

### Conversations et historique

- `GET /api/assistant/conversations` → pile des conversations de l'utilisateur
  (`id`, `title`, `history_mode`, `retention_days`, dates, `message_count`,
  `last_message`), de la plus récente à la plus ancienne.
- `POST /api/assistant/conversations` `{ "title"?: string }` → crée une
  nouvelle conversation (201).
- `GET /api/assistant/conversations/{id}` → `{ conversation, messages }`
  pour une conversation précise.
- `PUT /api/assistant/conversations/{id}` `{ "title"?, "history_mode"?,
  "retention_days"? }` → met à jour ses réglages.
- `DELETE /api/assistant/conversations/{id}` → `{ ok: true }` (messages
  compris).
- `GET /api/assistant/history` → historique global (compatibilité) ;
  `PUT /api/assistant/history/settings` change le mode par défaut et
  l'applique aux conversations existantes ; `DELETE /api/assistant/history`
  efface tout l'historique.

Par défaut, l'historique est conservé **30 jours** puis purgé automatiquement.
Le mode **éphémère** stoppe l'écriture des nouveaux messages ; l'utilisateur
peut effacer une conversation ou tout l'historique à tout moment.

### Mode de travail de l'agent

- `GET /api/agent/mode` → `{ mode: "accompagnement"|"preparation"|"veille"|"autonome",
  modes: [{ id, label, description }] }`
- `PUT /api/agent/mode` `{ "mode": "..." }` → même réponse (mode persisté
  sur l'utilisateur, 422 si inconnu). Réservé au rôle candidat (403 sinon).

Chaque mode a un effet vérifiable sur la priorité de `dashboard.next_action` :
`accompagnement` fait remonter d'abord la compétence à développer,
`preparation` et `autonome` font remonter l'adaptation du CV pour une
correspondance forte, `veille` fait remonter l'offre à examiner.

**Mode autonome** : à chaque visite du dashboard, l'agent prépare
automatiquement un CV ciblé pour la meilleure correspondance forte (≥75)
qui n'en a pas encore (au plus une par visite, trois candidates max), et
marque la candidature « CV préparé ». Le résultat est exposé dans
`dashboard.autonomous_prepared` : `{ job_id, job_title, company, score,
message }`. Le candidat relit puis soumet : l'envoi réel reste validé
humain (§47).

### Préférences de l'agent (point 13)

- `GET /api/agent/preferences` → réservé au candidat :
  `{ mode, prefs: { scope, frequency, validation, actions },
  modes, scopes, frequencies, validations, actions,
  channels, channels_href }`.
  - `scope` : `tous` | `secteur` | `region` ; filtre réellement les offres
    proposées par Mon agent (secteur principal ou localisation du profil).
  - `frequency` : `quotidienne` | `hebdomadaire` | `manuelle` ; les passes
    automatiques de digest et d'alertes respectent ce choix (manuelle =
    aucune passe auto, hebdomadaire = le lundi).
  - `validation` : `documents` | `toujours` ; la validation humaine de
    l'envoi reste obligatoire dans les deux cas. Le mode `autonome` exige
    `documents` (422 sinon).
  - `actions` : `prepare_cv`, `prepare_letter`, `prepare_interview`,
    `watch_jobs`, `alert_deadlines` (booléens). Une action désactivée est
    bloquée côté API (403) et filtrée dans l'inbox et les alertes.
  - `channels` : résumé en lecture seule des canaux de notification
    (`channels_href` pointe vers `/parametres-compte#notifications`).
- `PUT /api/agent/preferences` : mise à jour partielle des mêmes champs
  (le mode peut être inclus). 422 sur une valeur inconnue ou le mode
  autonome avec `validation=toujours` ; 403 pour un rôle non candidat.

Quel que soit le mode, l'agent prépare et le candidat valide : aucune
candidature n'est envoyée automatiquement (§47).

## 10. Learning : formations suivies et preuves vérifiables

Les cinq natures de lien (`link_kind`) disent **honnêtement** ce que le lien
ouvre ; aucune page d'accueil trompeuse n'est présentée comme la formation :

| `link_kind` | `link_kind_label` | Ce que le lien ouvre |
| --- | --- | --- |
| `exact` | Formation exacte | la page de la formation elle-même |
| `catalogue` | Catalogue du fournisseur | le catalogue du fournisseur (la formation y est listée) |
| `search` | Résultats de recherche | des résultats de recherche ciblés sur la compétence |
| `local` | Centre ou organisme (sur place) | un centre / organisme de formation (lien parfois absent) |
| `interne` | Activité guidée (dans la plateforme) | une activité guidée, sans lien externe (projet pratique) |

### GET /api/learning →

```text
{ learn_now: [{ skill, reason,
                resources: [{ key, title, provider,
                              type: "course"|"certification"|"project"|"free",
                              url?, link_kind, link_kind_label }] }],
  improve: [...],                // consolidation du domaine (même forme)
  learn_next: [...],
  progress: [{ skill, level, status: "verifiee"|"a_confirmer"|"en_progression",
               status_label, demand: int,
               evidences: [{ kind: "experience"|"project"|"certification"|"education", label }],
               next_step: string }],
  enrollments: [Enrollment],     // formations suivies (voir ci-dessous)
  stats: { total, in_progress, completed, verifiable, added_to_profile },
  proof_kinds: [{ value, label }],   // aucune|certificat|attestation|badge|portfolio|autre
  link_kinds:  [{ value, label }],   // exact|catalogue|search|local|interne
  statuses:    [{ value, label }] }  // commencee|en_cours|terminee (dans l'ordre)
```

Chaque ressource porte une **clé stable** `key` (dérivée de la compétence
et du titre) : le lien profond `/learning/{key}` ouvre la fiche exacte de
CETTE formation dans le frontend, pas la page générique du catalogue. La
clé ne change pas même si la ressource est réordonnée dans le référentiel.

`status = "verifiee"` : la compétence est appuyée par des preuves issues du
profil (expériences, projets, certifications) **et** des formations suivies
vérifiées. `next_step` donne l'action concrète pour renforcer la
vérifiabilité.

### Enrollment (formation suivie)

```text
{ id, skill, title, provider, url?, kind, link_kind, link_kind_label,
  status, status_label, started_at, completed_at?,
  proof_kind, proof_label, proof_reference, proof_note,
  verifiable: bool, added_to_profile: bool }
```

`verifiable` est vrai quand la formation est terminée ET qu'une pièce
demandant une référence (certificat, attestation, badge, portfolio, autre)
est fournie. La pièce est **déclarée** : aucune n'est inventée ni téléversée.

### POST /api/learning/enrollments → 201 `Enrollment`

Body : `{ skill, title, provider?, url?, kind?, link_kind? }`
Idempotent : rouvrir la même formation (même `skill` + `title`) met à jour le
lien et renvoie le suivi existant. L'ouverture d'une formation depuis la page
crée ce suivi (`status = "commencee"`).

### PATCH /api/learning/enrollments/{id} → `Enrollment`

Body partiel : `{ status?, proof_kind?, proof_reference?, proof_note? }`
`status = "terminee"` horodate `completed_at`. Si la pièce choisie exige une
référence et qu'elle manque → **400** (« Indiquez la référence de la pièce… »).
404 si le suivi appartient à un autre compte.

### DELETE /api/learning/enrollments/{id} → `{ deleted: true, id }`

Retire le suivi. Les preuves déjà rattachées au profil y restent : elles ont
été validées par le candidat.

### POST /api/learning/enrollments/{id}/to-profile → `{ enrollment, profile }`

**Validation humaine (§47)** : la formation terminée AVEC sa pièce devient une
expérience (`apprenticeship`) et une certification du profil maître, la pièce
et sa référence restant affichées. Rejouer l'appel n'ajoute pas de doublon.
400 si le profil n'existe pas, ou si la formation n'est pas vérifiable.

## 11. Carrières

`GET /api/careers` inclut pour chaque métier :
`related_jobs: [{ id, title, company, location, contract_type }]` (offres actives liées).

## 12. Administration (rôle `admin` uniquement, 403 sinon)

### GET /api/admin/stats → `{ users, profiles, jobs, applications, documents, learning_resources, open_reports, llm_enabled, smtp_enabled }`
### GET /api/admin/settings → `{ smtp, inbound, llm, aggregators, notifications }` (secrets JAMAIS renvoyés : `*_set: bool`)
### PUT /api/admin/settings/{group}: group ∈ `smtp | inbound | llm | aggregators | notifications`
Body : `{ "data": { ... } }` (fusion) → `{ {group}: config_masquée }`.
Un secret soumis vide (`""`) CONSERVE la valeur existante.

Configurations :

```text
smtp:        { provider: "smtp"|"brevo"|"resend", host, port, username,
               password*, api_key*, from_email, from_name, use_tls, enabled }
inbound:     { enabled, address, protocol: "imap"|"webhook",
               imap_host, imap_port, imap_username, imap_password*,
               imap_use_ssl, imap_mailbox, poll_seconds,
               webhook_secret*, fallback_email }
llm:         { provider: "rules"|"openai", model, base_url, api_key*, enabled }
aggregators: { telegram: { bot_token*, chat_id, enabled },
               whatsapp: { provider, api_key*, phone_number_id, enabled } }
notifications: { digest_enabled, digest_hour }
```

`*` = secret (masqué en lecture).

`inbound.address` est l'adresse interne affichée sur le visuel public et
les pages d'offre. `inbound.fallback_email` reçoit les candidatures quand
l'offre ne porte pas d'adresse RH. Modifier `inbound` démarre ou arrête
la relève IMAP sans redémarrer le serveur.

### POST /api/admin/test-llm → `{ ok, detail }` (ping réel du LLM configuré)
### POST /api/admin/test-smtp → `{ ok, detail }` (test du transport e-mail)
Body optionnel : `{ "data": { provider, host, port, username, password,
api_key, from_email, from_name, use_tls, enabled } }`. Le test utilise ces
valeurs même avant enregistrement ; un secret vide réutilise la valeur
stockée. Sans body, la configuration enregistrée est utilisée.
Pour `smtp` : poignée de main + STARTTLS + LOGIN. Pour `brevo` ou `resend` :
appel HTTPS en lecture seule sur le compte, sans envoi de message. Les API
HTTPS passent par le port 443 et restent compatibles avec Render, qui bloque
les ports SMTP 25, 465 et 587.
### POST /api/admin/test-imap → `{ ok, detail }` (connexion et dossier IMAP en lecture)
Body optionnel : `{ "data": { imap_host, imap_port, imap_username,
imap_password, imap_use_ssl, imap_mailbox } }`. Le test utilise ces valeurs
même avant enregistrement ; un `imap_password` vide réutilise le secret
stocké. Sans body, la configuration enregistrée est utilisée.
### GET /api/admin/inbound-emails?status=&limit= → journal des messages reçus
`[{ id, message_id, source, sender_email, sender_name, subject, status,
routing, job_id?, job_title, company, application_id?, user_id?,
user_email, account_created, forwarded_to, forward_email_sent,
access_email_sent, attachments_count, attachment_names, detail,
created_at, processed_at }]`. `status` ∈ `transmise | recue | non_routee`.
### POST /api/admin/inbound-emails/{id}/resend-access → `{ ok, detail }`
Renvoie des accès à un candidat créé automatiquement par e-mail, avec un
nouveau mot de passe provisoire. Le mot de passe n'est remplacé qu'après
un envoi réussi ; `400`-like `{ok:false}` si SMTP n'est pas configuré.
### GET /api/admin/connecteurs → catalogue formalisé V1/V2/V3 :

```text
[{ id, name, kind, status: "operationnel"|"configure"|"roadmap", phase, description, configurable }]
```

### GET /api/admin/jobs: liste complète (vue back-office)
### POST /api/admin/jobs: création (title, company, domain_id?, specialty_id?, …, required_skills, source_name, source_url, apply_channel?, apply_instructions?, apply_email?, apply_keywords?)
### PUT /api/admin/jobs/{id}: mise à jour partielle
### DELETE /api/admin/jobs/{id}: suppression (candidatures/documents liés supprimés, photo effacée)
### POST /api/admin/jobs/{id}/photo: photo facultative (multipart `file`, JPG/PNG/WebP, 5 Mo max)
### DELETE /api/admin/jobs/{id}/photo: retire la photo

`apply_channel` surcharge le canal déduit (`platform`/`external`),
`apply_instructions` est montré au candidat, `apply_email` déclenche la
transmission automatique de la candidature par e-mail (voir §6) et sert
d'adresse RH pour les candidatures reçues par e-mail. `apply_keywords`
est une liste de mots-clés de routage, utilisée après la référence
`OS-XXXX` (voir §6ter). Les listes admin et recruteur renvoient
`apply_email`, `apply_keywords`, `email_reference` et `poster_url`.

### Formations (catalogue §19, console admin)

- `GET /api/admin/learning?skill=` → `[{ id, skill, title, provider,
  type, url, source: "referentiel"|"admin", hidden: bool }]`.
- `POST /api/admin/learning { skill, title, provider?, type, url? }` →
  201. `type` ∈ `course | certification | project | free`. La formation
  est créée `source: "admin"` : la synchronisation du démarrage (alignée
  sur `data/learning_resources.json`) ne l'écrase ni ne la supprime
  jamais. Doublon (compétence + intitulé) → 400.
- `PUT /api/admin/learning/{id}` : modifie une formation, y compris une
  ligne du référentiel. Une ligne `referentiel` modifiée devient
  `source: "admin"` pour que le lien corrigé ne soit pas écrasé au
  démarrage suivant.
- `DELETE /api/admin/learning/{id}` : supprime définitivement une ligne
  `admin` ; retire du catalogue une ligne `referentiel` (marquée
  `hidden: true`, rétablissable).
- `POST /api/admin/learning/{id}/restore` → rétablit une formation
  retirée.
- Le catalogue proposé aux candidats (`/api/learning`) et à l'assistant
  est lu en base : une ligne masquée n'est jamais proposée, un lien
  corrigé reste celui choisi par l'admin.

### Suspension de comptes (modération)

- `PUT /api/admin/users/{id}/ban { reason }` : suspend un compte
  candidat ou recruteur ; motif OBLIGATOIRE (5 caractères minimum),
  conservé et communiqué. Un compte `admin` ne peut être suspendu
  (400), ni soi-même.
- `DELETE /api/admin/users/{id}/ban` : lève la suspension.
- Effet : connexion refusée (403 avec le motif) et TOUTE l'API
  authentifiée verrouillée pour le jeton en cours.
- `GET /api/admin/users` expose `is_banned` et `ban_reason` par compte.

### Recours après suspension

Le compte suspendu n'est jamais supprimé : la personne peut contester.

- `POST /api/auth/appeal { email, password, message }` : recours public
  (identité prouvée par le mot de passe). `message` : 20 à 2000
  caractères. 401 si les identifiants sont faux, 400 si le compte n'est
  pas suspendu. Un seul recours ouvert à la fois ; une nouvelle demande
  met à jour le message du recours en attente. Si l'administration a
  demandé un complément, la réponse repasse le recours en `pending` et
  conserve la demande dans l'historique.
  → `{ id, status: "pending"|"complement"|"accepted"|"rejected", message,
       created_at, reviewed_at?, admin_note? }`
- La connexion refusée indique l'état réel du recours : en examen,
  complément attendu avec son motif, ou refusé avec son motif.
- `GET /api/admin/appeals` : page dédiée aux recours. Filtres :
  `status` (`open` = `pending` + `complement`, ou un statut précis),
  `kind` (`suspension`), `user` (nom ou e-mail), `q` (nom, e-mail, motif
  de suspension ou message), `date_from`, `date_to`, `limit`.
  Chaque ligne contient le contexte du compte (`user_role`,
  `user_created_at`, `is_banned`, `applications_count`,
  `documents_count`, `ban_reason`), l'ancienneté (`age_hours`,
  `is_open`), le fil `history` et le nom du décideur
  (`reviewed_by_name`).
- `PUT /api/admin/appeals/{id} { decision: "accepted"|"rejected"|
  "complement", note }` : traite un recours ouvert. `note` obligatoire
  (10 caractères minimum, 422 sinon). `accepted` lève la suspension
  (données intactes) ; `rejected` la maintient ; `complement` maintient
  la suspension et attend une réponse du candidat. 400 si le recours est
  déjà clos. Chaque décision est horodatée, ajoutée à `history`, tracée
  dans le journal admin (`AdminNotificationLog`, catégorie `appeal`) et
  notifiée par e-mail sur le canal activé du candidat. La décision
  apparaît aussi dans `/api/notifications` (kind `appeal`).
- Interface : page admin `/admin/recours`, entrée « Recours » de la
  navigation ; la gestion des utilisateurs renvoie vers cette page.

Côté recruteur, mêmes routes pour ses propres offres :
`POST/DELETE /api/recruiter/jobs/{id}/photo` (404 si l'offre n'est pas la sienne).

Comptes seed : `demo@orientskill.cm / demo1234` (candidat) ·
`admin@orientskill.cm / admin1234` (administrateur).

## 13. Export PDF

`GET /api/documents/{id}/export?format=pdf` produit un PDF A4 mis en page
professionnellement (moteur `fpdf2` ; `reportlab` reste le repli du rendu
markdown générique). CV : bandeau, photo optionnelle, compétences ciblées,
expériences datées ; lettre : conventions épistolaires FR (ciblée ou
généraliste, destinataire `[Nom de l'entreprise]`/`[Ville]`). Chaque
couleur d'accent dispose d'une famille complète (bandeau sombre, accent
vif, accent foncé), y compris les couleurs libres `#RRGGBB` : le
changement de couleur est visible sur le PDF. Le modèle « ats » garde sa
charte bleu nuit / turquoise par défaut, mais suit une couleur explicitement
choisie. Le rendu ATS suit le gabarit Python de référence : une colonne,
intitulés standards en majuscules (PROFIL, COMPÉTENCES, EXPÉRIENCE
PROFESSIONNELLE, PROJETS, CERTIFICATIONS, FORMATION, LANGUES), dates en
mois en toutes lettres, ligne de domaines sous le titre.
Repli markdown si la bibliothèque est absente.

## 13bis. Programmes publics (`GET /api/institutional`)

Référentiel restructuré par INSTITUTION, puis par dispositif :
`minfopra` (concours directs, intégration), `minesup` (universités,
écoles, avis de concours), `minefop` (FNE, bourses de formation),
`ong` (emplois, stages), `mindef` (armée, gendarmerie, BIR, garde
présidentielle, EMIA, armées étrangères), `dgsn` (police),
`appels_projets` (par ministère). `backend/data/institutional_offers.json`
fait foi : il est resynchronisé au démarrage (fiches ajoutées, mises à
jour, retirées). Champ `url` facultatif (null si aucun site officiel
n'est renseigné).

Chaque fiche expose `documents: [{ key, label, url }]`: les **PDF
officiels** joints par l'administration (avis, communiqués), servis tels
quels par `GET /api/institutional/{id}/documents/{key}`. La liste est
vide par défaut : la plateforme n'invente ni ne recherche aucun document.

**Ajouts de l'administration** : une fiche créée ou modifiée dans la
console (`source = "admin"`) n'est **jamais** écrasée ni supprimée par la
resynchronisation du référentiel ; seules les fiches issues du
référentiel suivent le JSON. Les PDF joints sont déposés depuis la
console (voir §18).

### GET /api/institutional/minesup → `[UniversitéMinesup]`

```text
UniversitéMinesup {
  id, slug, name, short_name, city, region, description,
  website, source_url,
  schools: [{ id, name, short_name, kind, admission, eligibility, url, deadline }]
}
```

Catalogue à deux niveaux de l'explorateur MINESUP. La hiérarchie est
portée par les tables `minesup_universities` et `minesup_schools`, jamais
devinée depuis un texte libre. Le seed de démonstration
(`backend/data/minesup_universities.json`) ne s'exécute que si la table
des universités est vide : il n'écrase jamais les corrections de
l'administration. Les calendriers restent ceux annoncés par le MINESUP.

## 14. Sources & collecte multi-source (V2, admin)

- `GET/POST /api/admin/sources`, `PUT/DELETE /api/admin/sources/{id}`:
  connecteurs RSS/JSON. Champs : `name`, `kind` (`rss|json`), `url`,
  `sector`, `enabled`, `interval_minutes` (5 à 1440, défaut 60).
- `POST /api/admin/sources/test {kind, url}` → `{ ok, items, sample, detail }`
  lit un flux sans créer de source.
- `POST /api/admin/sources/{id}/run` → `{ source, imported, skipped, items,
  duration_ms, not_modified?, error? }` (dédup incluse) ;
  `POST /api/admin/sources/run-all` → liste de ces résultats pour les
  connecteurs actifs, téléchargements parallélisés.
- Chaque source expose sa **fiabilité** : `runs`, `failures`,
  `offers_imported/skipped`, `last_run_at`, `last_status`, `last_error`,
  `last_items`, `last_duration_ms`, `reliability_pct`, `health`
  (`ok|warning|error|idle|off`), `next_run_at`, `is_due` (§51).
- Les sources activées sont collectées automatiquement par le planificateur
  selon leur intervalle. Les flux exposant `ETag` / `Last-Modified` sont
  interrogés conditionnellement ; un flux inchangé répond `304` et n'est
  pas reparsé. Désactivable par `SOURCE_SCHEDULER_ENABLED=0`.
- La date de publication d'origine du flux est conservée dans
  `Job.published_at` ; la déduplication combine URL canonique et clé
  normalisée titre/entreprise/lieu.
- `POST /api/admin/import-url {url}` → brouillon d'offre extrait du balisage
  JSON-LD public de la page (LinkedIn ou autre) : à valider avant publication.

## 15. Shortlists & candidatures côté recruteur (V2)

- `GET /api/recruiter/candidates?skills=&q=&region=&sector=&domain_id=&specialty_id=&verified_only=`
  → `[RecruiterCandidate]` : recherche explicable (§21). Chaque entrée
  contient les faits du profil validé (titre, résumé, compétences avec
  niveau et source, expériences, formations, certifications, langues,
  préférences, compteurs) et `match: { score, covered, partial, missing }`.
  Aucune coordonnée personnelle n'est exposée.
- `GET /api/recruiter/candidates/{id}` → `RecruiterCandidate` : carte de
  profil complète, avec `photo_url` quand le talent a une photo.
- `GET /api/recruiter/candidates/{id}/photo` → image (rôle recruteur
  uniquement ; `404` sans photo).
- `GET /api/recruiter/candidates/{id}/cv` → PDF : uniquement le CV
  généraliste que le talent a explicitement partagé. Le PDF est régénéré
  depuis le profil validé avec le modèle et la couleur du document choisi.
  `404` si le partage est désactivé ou si le document n'est pas un CV
  généraliste.
- `GET/POST /api/recruiter/shortlists`, `DELETE /api/recruiter/shortlists/{id}`,
  `POST/DELETE /api/recruiter/shortlists/{id}/items`: listes privées par entreprise.

### Invitations à un entretien

- `POST /api/recruiter/interviews` :
  `{ candidate_id, job_id, slot_at, duration_min?, subject, message }`.
  Le candidat doit être dans une shortlist du recruteur (400 sinon) et
  l'offre doit appartenir à son entreprise (403).
  `slot_at` : date et heure futures, exprimées en heure du Cameroun
  (UTC+1). `subject` : 3 à 200 caractères, `message` : 20 à 4000
  caractères. Un e-mail personnalisé est envoyé au candidat (identité
  réelle du poste et de l'entreprise, créneau lisible, liens profonds
  accepter / autre créneau, fichier `.ics` joint). `email_sent: false`
  signale simplement que SMTP n'est pas configuré : l'invitation reste
  disponible dans l'espace du candidat.
- `GET /api/recruiter/interviews` → invitations envoyées, avec la réponse
  (`status: "pending"|"accepted"|"declined"`, `candidate_note`,
  `calendar_url`).
- `GET /api/interviews` (candidat) → invitations reçues, `calendar_url`.
- `GET /api/interviews/{token}` : vue publique de l'invitation (le lien de
  l'e-mail fonctionne avant connexion ; aucune donnée personnelle du
  candidat n'est exposée).
- `GET /api/interviews/{token}/calendar.ics` : fichier iCalendar public
  (le jeton fait office de secret). `DTSTART`/`DTEND` en UTC, statut
  `TENTATIVE` (proposé), `CONFIRMED` (accepté) ou `CANCELLED` (autre
  créneau demandé). Même fichier joint aux e-mails d'invitation et de
  réponse.
- `POST /api/interviews/{token}/respond { decision: "accepted"|"declined", note? }` :
  réservé au candidat invité (403 sinon, 400 si déjà répondu). La réponse
  part aussi en message interne au recruteur, avec le `.ics` à jour.

`PUBLIC_BASE_URL` (variable d'environnement, défaut
`http://localhost:5190`) construit les liens profonds des e-mails ;
à définir en production.

- `GET /api/recruiter/applications` → `[RecruiterApplication]` :
  candidatures reçues, avec `candidate_photo_url`,
  `apply_channel`, `apply_url`, `apply_email`, `apply_instructions`
  (lien de postulation quand la candidature se fait sur le site de
  l'entreprise).
- `PATCH /api/recruiter/applications/{id} {status, reason?}`: **statut
  partagé**. Transitions autorisées : `envoyee` → `en_attente`|`entretien`|
  `refusee` ; `en_attente` → `entretien`|`refusee` ; `entretien` → `offre`|
  `refusee` ; `offre` → `refusee`. Le recruteur ne peut ni accepter une offre
  à la place du candidat, ni retirer une candidature. Toute autre transition
  est refusée en `403`. La mise à jour est journalisée avec l'entreprise et
  le motif éventuel (visible du candidat), et déclenche sa notification
  multi-canaux.

### Notifications par événement (§25, §52)

- `GET /api/profile/notifications` → préférences de l'utilisateur :
  canaux (`email_enabled`, `email`, `telegram_*`, `whatsapp_*`),
  `email_frequency` (`immediate` | `daily`) et `events` : opt-in e-mail
  **par événement** (`false` = l'information reste dans l'application).
  La réponse contient aussi `role`, `event_types` (libellés) et
  `event_catalog` (liste `{key, label, description, group, critical}`)
  **filtrés selon le rôle connecté** :
  - candidat : `new_match`, `expiring`, `message`, `application`,
    `interview`, `verification_decision`, `agent` ;
  - recruteur : `new_application`, `candidate_message`,
    `interview_response`, `job_published`, `job_expiring`,
    `company_verification` ;
  - admin : `verification_request`, `appeal`, `report`,
    `ingestion_failure`, `critical_alert`.
- `PUT /api/profile/notifications { ...canaux, email_frequency?, events?:
  {clé: bool} }` : fusion (mise à jour partielle possible). Les clés
  d'événements d'un autre rôle sont ignorées. `email_frequency` invalide
  → `422`.
- Fréquence des offres : `immediate` = passe horaire, fenêtre d'une heure ;
  `daily` = fenêtre de 24 h, après `digest_hour` configuré par l'admin.
  Dans les deux cas, **un seul e-mail d'offres par jour et par candidat** ;
  les offres déjà envoyées sont dédupliquées dans `notification_log`.
  Les autres correspondances restent dans l'inbox.
- Événements déclencheurs : message d'un recruteur (messagerie), mise à
  jour de candidature, nouvelle candidature reçue (recruteur), réponse à
  une invitation (recruteur), publication et expiration d'offre
  (recruteur), alertes de l'équipe admin (routage par catégorie).
- E-mails critiques (`critical_alert`, sécurité, compte) : toujours
  envoyés sur l'adresse du compte, même si le canal e-mail ou la catégorie
  est désactivé. Ils n'incluent pas de lien de désabonnement.
- `GET /api/profile/notifications/unsubscribe?token=...` : désabonnement
  en un clic, **sans authentification**, via un jeton HMAC signé
  (`SECRET_KEY`). Il désactive uniquement les alertes emploi du rôle
  (`new_match`, `expiring`, `agent` côté candidat ; `job_expiring` côté
  recruteur). Les messages transactionnels et les e-mails critiques
  restent envoyés. Réponse HTML de confirmation ; jeton invalide → `400`.
- Les e-mails non critiques contiennent un lien vers
  `/parametres-compte#notifications` ; les alertes emploi ajoutent le lien
  de désabonnement signé.
- `POST /api/profile/notifications/test` : envoi manuel sur les canaux
  activés (ignore les opt-in par événement : c'est un test).

## 16. Cloisonnement des rôles

Les pages sont strictement séparées par rôle (candidat / recruteur / admin).
L'admin n'a pas de profil candidat ; un recruteur ne voit que son espace ;
les exceptions neutres sont la messagerie interne et les **Paramètres**
(MFA, notifications, vérification de profil), accessibles à tous les rôles.

## 17. Vérification de profil (refonte)

- Dépôt en **deux temps** : sélection du fichier → aperçu → confirmation
  explicite (le fichier n'est envoyé qu'au clic « Confirmer »).
- Côté admin : `GET /api/admin/verifications` inclut le **profil déclaré**
  (titre, localisation, diplômes, certifications) pour la comparaison
  profil ↔ pièce.
- `POST /api/admin/verifications/{id}/approve {note?}` et
  `POST /api/admin/verifications/{id}/reject {note}` : **le motif du rejet
  est OBLIGATOIRE (≥ 5 caractères)** et communiqué au candidat.
- Chaque décision crée une notification in-app `verification` (validée ou
  refusée, avec le motif). Un e-mail part uniquement si le candidat a
  activé `verification_decision` dans ses préférences ; l'envoi éventuel
  est journalisé dans `notification_log`.

## 18. V3 : Intelligence (admin)

- `GET /api/admin/institutional-dashboard` : agrégats **anonymisés**
  (volume d'usage, offre/demande de compétences, écarts avec ratio de
  tension, régions, secteurs, candidatures par étape).
- `GET /api/admin/skill-graph` : points d'entrée (compétences
  structurantes). `GET /api/admin/skill-graph?skill=X` : nœud complet
  (métiers, offres, vivier par niveau, compétences voisines, formations).
- `GET/POST/PUT/DELETE /api/admin/public-content/institutional[/{id}]` et
  `/api/admin/public-content/entrepreneurship[/{id}]` : gestion des
  contenus Programmes publics et Entrepreneuriat.
- `POST /api/admin/public-content/institutional/{id}/documents` (multipart
  `file` + `label`) : joint un PDF officiel à un programme, facultatif,
  plusieurs documents possibles, 15 Mo max, PDF uniquement.
- `DELETE /api/admin/public-content/institutional/{id}/documents/{key}` :
  retire le PDF (fichier hébergé effacé).
- `GET /api/admin/public-content/minesup` → catalogue complet (universités
  et écoles, y compris `source` et `sort_order`).
- `POST/PUT/DELETE /api/admin/public-content/minesup/universities[/{id}]` :
  création, correction et suppression d'une université (la suppression
  retire aussi ses écoles).
- `POST /api/admin/public-content/minesup/universities/{id}/schools`,
  `PUT/DELETE /api/admin/public-content/minesup/schools/{id}` : gestion
  des grandes écoles et concours rattachés. Toute correction passe la
  fiche en `source = "admin"` : le seed de démarrage ne la remplacera pas.

## 19. Entrepreneuriat (§11bis)

- `GET /api/entrepreneurship?kind=concours|accompagnement|financement|formation`
  → `{ resources: [{ id, kind, kind_label, title, description, organizer, url, sectors }],
       bank_prep: [{ step, detail }],
       financing_institutions: [{ name, type, finances, conditions, url }] }`
- `GET /api/entrepreneurship/guidance` → `{ category, category_label, introduction,
  opportunities: string[], steps: string[] }` : pistes « comment entreprendre dans
  MON domaine », calculées depuis le profil validé. **Jamais une promesse de réussite.**
- `GET /api/entrepreneurship/profile` → lecture entrepreneuriale du profil validé :
  `{ has_profile, profile_title, groups: [{ key, label, items: [{ name, state:
  "covered"|"partial"|"missing", proficiency }], covered, partial, total }],
  covered_count, partial_count, missing_count, total, coverage,
  trade_skills: [{ name, category }], scored }`.
  Le référentiel (`ENTREPRENEUR_SKILL_GROUPS`) est un **sous-ensemble de notre
  taxonomie de compétences** : aucun nom inventé (§47). `coverage` mesure la part du
  référentiel couverte par les compétences déclarées (une compétence de niveau
  débutant compte à moitié) ; `trade_skills` liste les compétences métier du porteur
  qui n'appartiennent pas au référentiel (§48).
- `POST /api/entrepreneurship/business-plan` `{ activity, target, capital, location }`
  → `Document` (`kind = "business_plan"`), construit **uniquement** depuis le
  formulaire et le profil validé.

L'assistant (`POST /api/assistant`) possède un **intent entrepreneuriat** : il
renvoie le domaine d'atout, les pistes, les compétences entrepreneuriales déjà
couvertes, les financements et les programmes répertoriés, avec des liens
`/entrepreneurship` (traduit côté frontend en `/entrepreneuriat`).

## Codes d'erreur

`401` non authentifié · `403` interdit · `404` inexistant · `422` validation · `400` métier (ex. profil absent).
Format erreur : `{ "detail": string }`.
