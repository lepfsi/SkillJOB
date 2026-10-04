# Contrat d'API — OrientSkill AI (MVP)

Backend : FastAPI, préfixe `/api`, base locale `http://localhost:8000`.
Frontend : React + Vite (proxy `/api` → `localhost:8000`), port `5173`.
Auth : JWT dans l'en-tête `Authorization: Bearer <token>` (stocké en `localStorage` côté frontend, clé `orientskill_token`).
Format : JSON UTF-8. Toutes les listes supportent la pagination simple `?skip=&limit=` (défaut limit=50).

## 1. Auth

### POST /api/auth/register
Body : `{ "email": string, "password": string, "full_name": string }`
→ `201 { "token": string, "user": User }`

### POST /api/auth/login
Body : `{ "email": string, "password": string }`
→ `{ "token": string, "user": User }`

### GET /api/auth/me → `User`

```text
User { id, email, full_name, role: "candidate"|"recruiter"|"admin", created_at }
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
  preferences:   { sectors: string[], target_roles: string[], contract_types: string[], remote_ok: bool }
}
```

### PUT /api/profile
Body : `Profile` (complet ou partiel) → `Profile` (profil maître mis à jour)

### POST /api/profile/import-cv
Accepte soit JSON `{ "text": "contenu du CV" }`, soit `multipart/form-data` avec un fichier `.pdf` ou `.txt` (champ `file`).
→ `{ "draft": Profile, "report": { skills_found: int, experiences_found: int, certifications_found: int, degrees_found: int, career_fields: string[] } }`

Le brouillon **n'est pas enregistré** : l'utilisateur valide via `PUT /api/profile` (principe "validation humaine", §47).

### GET /api/questionnaire → `{ steps: [ { id, title, questions: [{ id, label, type: "text"|"textarea"|"multi_choice"|"choice"|"list", options?: string[] }] } ] }`

### POST /api/questionnaire/submit
Body : `{ "answers": { "<question_id>": any } }` → `{ "draft": Profile, "report": {...} }` (même format que l'import CV)

## 3. Compétences

### GET /api/skills/taxonomy → `[{ name, category, aliases: string[] }]`
### GET /api/skills/market → `[{ name, demand_count, trend: "up"|"stable"|"down", pct_change: int }]` (tendances issues des offres)

## 4. Carrières / Orientation (Career + Orientation Intelligence)

### GET /api/careers
→ `[{ id, title, family, description, required_skills: [{ name, importance: "core"|"preferred" }],
      match: { score: 0-100, covered: string[], missing: string[], accessibility: "immediate"|"with_upskilling"|"long_term",
               recommended_actions: string[] } }]` (trié par score décroissant)

## 5. Offres (Job Intelligence) + Matching

### GET /api/jobs?search=&sector=&location=&contract_type=&min_score=

→ `[{ id, title, company, location, sector, contract_type: "CDI"|"CDD"|"Stage"|"Freelance"|"Apprentissage",
      published_at, source: { name, url }, match_score: 0-100 | null }]`

### GET /api/jobs/{id} → `{ job: Job, match: Match | null }`

```text
Job { id, title, company, location, sector, contract_type, description, requirements: string,
      required_skills: [{ name, importance: "core"|"preferred", level?: string }],
      published_at, deadline?, source: { name, url }, }

Match {
  score: 0-100, level: "forte"|"moyenne"|"faible",
  covered: string[], partial: string[], missing: string[],
  strengths: string[], explanation: string, recommended_actions: string[]
}
```

Le score est **explicable** (§12) : jamais un simple pourcentage opaque.

## 6. Candidatures (mini-ATS personnel)

### GET /api/applications → `[ Application ]`
### POST /api/applications `{ "job_id": int }` → `Application`
### PATCH /api/applications/{id} `{ "status": ... }` → `Application`

```text
Application { id, user_id, job_id, job: JobSummary,
  status: "identifiee"|"cv_prepare"|"envoyee"|"en_attente"|"entretien"|"offre"|"acceptee"|"refusee",
  timeline: [{ at, event }], documents: [{ id, kind: "cv"|"cover_letter", title }] }
```

## 7. Documents (CV Intelligence + Application Assistant)

### POST /api/jobs/{id}/cv → `Document` (CV ciblé, génération règles/templating, **sans invention**)
### POST /api/jobs/{id}/cover-letter → `Document`
### POST /api/jobs/{id}/interview-prep → `{ likely_questions: string[], technical: string[], behavioral: string[], pitch: string, prep_tips: string[] }`
### GET /api/documents → `[ Document ]`
### GET /api/documents/{id} → `Document`
### GET /api/documents/{id}/export?format=md|pdf → téléchargement (PDF si `reportlab` dispo, sinon markdown)

```text
Document { id, kind: "cv"|"cover_letter", title, content_markdown: string, job_id?, created_at }
```

## 8. Dashboard / Inbox / Marché / Learning

### GET /api/dashboard

```text
{ name, new_opportunities: int, strong_matches: int, skills_to_improve: string[],
  ongoing_applications: int, interviews_to_prepare: int,
  market_trends: [{ name, trend, pct_change }],
  next_action: { label, type: "adapt_cv"|"learn"|"apply"|"prepare_interview", job_id?: int, skill?: string } }
```

### GET /api/inbox → `[{ id, at, kind: "new_job"|"strong_match"|"trend"|"learning"|"application", message, job_id? }]` (les événements sont calculés, pas nécessairement persistés)

### GET /api/market/trends

```text
{ top_skills: [{ name, count }], trending_up: string[], trending_down: string[],
  sectors: [{ name, offers: int }], emerging: string[] }
```

### GET /api/learning

```text
{ learn_now: [{ skill, reason, resources: [{ title, provider, type: "course"|"certification"|"project"|"free", url? }] }],
  learn_next: [...], progress: [{ skill, status }] }
```

## 9. Assistant conversationnel

### POST /api/assistant
Body : `{ "message": string, "history": [{ "role": "user"|"assistant", "content": string }] }`
→ `{ "reply": string, "suggestions": string[], "links": [{ label, href }] }`

Moteur hybride : réponses par règles ancrées sur les données réelles, suggestions DYNAMIQUES calculées depuis l'état du profil et du marché ; bascule vers un LLM si configuré via l'admin (sinon fallback règles). Jamais de données inventées.

## 10. Learning (progression vérifiable)

`GET /api/learning` →

```text
{ learn_now: [...], learn_next: [...],
  progress: [{ skill, level, status: "verifiee"|"a_confirmer"|"en_progression",
               status_label, demand: int,
               evidences: [{ kind: "experience"|"project"|"certification"|"education", label }],
               next_step: string }] }
```

`status = "verifiee"` : la compétence est appuyée par des preuves issues du
profil (expériences, projets, certifications). `next_step` donne l'action
concrète pour renforcer la vérifiabilité.

## 11. Carrières

`GET /api/careers` inclut pour chaque métier :
`related_jobs: [{ id, title, company, location, contract_type }]` (offres actives liées).

## 12. Administration (rôle `admin` uniquement, 403 sinon)

### GET /api/admin/stats → `{ users, profiles, jobs, applications, documents, learning_resources, llm_enabled, smtp_enabled }`
### GET /api/admin/settings → `{ smtp, llm, aggregators }` (secrets JAMAIS renvoyés : `*_set: bool`)
### PUT /api/admin/settings/{group} — group ∈ `smtp | llm | aggregators`
Body : `{ "data": { ... } }` (fusion) → `{ {group}: config_masquée }`.
Un secret soumis vide (`""`) CONSERVE la valeur existante.

Configurations :

```text
smtp:        { host, port, username, password*, from_email, use_tls, enabled }
llm:         { provider: "rules"|"openai", model, base_url, api_key*, enabled }
aggregators: { telegram: { bot_token*, chat_id, enabled },
               whatsapp: { provider, api_key*, phone_number_id, enabled } }
```

`*` = secret (masqué en lecture).

### POST /api/admin/test-llm → `{ ok, detail }` (ping réel du LLM configuré)
### POST /api/admin/test-smtp → `{ ok, detail }` (poignée de main SMTP + STARTTLS + LOGIN)
### GET /api/admin/connecteurs → catalogue formalisé V1/V2/V3 :

```text
[{ id, name, kind, status: "operationnel"|"configure"|"roadmap", phase, description, configurable }]
```

### GET /api/admin/jobs — liste complète (vue back-office)
### POST /api/admin/jobs — création (title, company, …, required_skills, source_name, source_url)
### PUT /api/admin/jobs/{id} — mise à jour partielle
### DELETE /api/admin/jobs/{id} — suppression (candidatures/documents liés supprimés)

Comptes seed : `demo@orientskill.cm / demo1234` (candidat) ·
`admin@orientskill.cm / admin1234` (administrateur).

## 13. Export PDF

`GET /api/documents/{id}/export?format=pdf` produit un PDF A4 mis en page
professionnellement (CV : en-tête, compétences ciblées, expériences datées ;
lettre : conventions épistolaires FR) via `reportlab` (installé par défaut).
Repli markdown si la bibliothèque est absente.

## 14. Sources & collecte multi-source (V2, admin)

- `GET/POST /api/admin/sources`, `PUT/DELETE /api/admin/sources/{id}` — connecteurs RSS/JSON.
- `POST /api/admin/sources/{id}/run` → `{imported, skipped}` (dédup incluse) ;
  `POST /api/admin/sources/run-all` → tous les connecteurs actifs.
- Chaque source expose sa **fiabilité** : runs, failures, offers_imported/skipped,
  last_run_at, last_status (§51).
- `POST /api/admin/import-url {url}` → brouillon d'offre extrait du balisage
  JSON-LD public de la page (LinkedIn ou autre) : à valider avant publication.

## 15. Shortlists & candidatures côté recruteur (V2)

- `GET/POST /api/recruiter/shortlists`, `DELETE /api/recruiter/shortlists/{id}`,
  `POST/DELETE /api/recruiter/shortlists/{id}/items` — listes privées par entreprise.
- `PATCH /api/recruiter/applications/{id} {status}` — **statut partagé** :
  la mise à jour est journalisée dans la timeline (visible du candidat) et
  déclenche sa notification multi-canaux.

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

## 18. V3 — Intelligence (admin)

- `GET /api/admin/institutional-dashboard` : agrégats **anonymisés**
  (volume d'usage, offre/demande de compétences, écarts avec ratio de
  tension, régions, secteurs, candidatures par étape).
- `GET /api/admin/skill-graph` : points d'entrée (compétences
  structurantes). `GET /api/admin/skill-graph?skill=X` : nœud complet
  (métiers, offres, vivier par niveau, compétences voisines, formations).
- `GET/POST/PUT/DELETE /api/admin/public-content/institutional[/{id}]` et
  `/api/admin/public-content/entrepreneurship[/{id}]` : gestion des
  contenus Programmes publics et Entrepreneuriat.

## Codes d'erreur

`401` non authentifié · `403` interdit · `404` inexistant · `422` validation · `400` métier (ex. profil absent).
Format erreur : `{ "detail": string }`.
