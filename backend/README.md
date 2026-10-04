# OrientSkill AI — Backend MVP

Plateforme d'intelligence professionnelle pour jeunes Camerounais (projet MINJEC).
Backend FastAPI + SQLAlchemy 2 (SQLite) + Pydantic v2, conforme au contrat
`docs/API_CONTRACT.md`.

## Lancement

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows (git-bash) ; .venv\Scripts\activate.bat en cmd
pip install -r requirements.txt
python -m app.main              # crée skilljob.db + seed automatique si base vide
```

L'API écoute sur http://localhost:8000 (docs interactive : `/docs`).

Au premier démarrage, `python -m app.main` (ou uvicorn) :
- crée les tables SQLite (`backend/skilljob.db`) ;
- si la base est vide, charge `data/skills_taxonomy.json`, `data/careers.json`,
  `data/jobs_seed.json`, `data/learning_resources.json` ;
- crée l'utilisateur démo **`demo@orientskill.cm` / `demo1234`** avec un profil
  « Technicien support IT / réseaux junior » complet (expériences informelles
  reconnues) et 2 candidatures.

## Tests

```bash
pip install pytest httpx
python -m pytest tests -q
```

## Architecture

```
backend/
├── requirements.txt
├── app/
│   ├── main.py          app FastAPI, CORS, routers, seed au démarrage
│   ├── config.py        SECRET_KEY, DATABASE_URL, LLM_PROVIDER, LLM_API_KEY (env)
│   ├── database.py      engine / SessionLocal / Base / get_db
│   ├── security.py      PBKDF2 (hashlib) + JWT (PyJWT) + dépendances auth
│   ├── models.py        User, Profile, Skill, Career, Job, Application, Document, LearningResource
│   ├── schemas.py       schémas Pydantic alignés sur le contrat d'API
│   ├── api/             routers (auth, profile, skills, careers, jobs,
│   │                    applications, documents, dashboard, market, learning, assistant)
│   └── services/        skills_taxonomy, cv_extractor, questionnaire, matching,
│                        orientation, cv_builder, market, learning, assistant,
│                        eventlog, profile_store
├── data/                taxonomie (≥60 skills), métiers (≥12), offres (≥20), ressources
└── tests/               tests d'intégration (pytest + TestClient)
```

## Principes

- **Pas d'invention (§47)** : CV et lettres n'utilisent que le profil validé.
- **Score explicable (§12)** : chaque match détaille couvertes / partielles /
  manquantes, points forts, explication en français et actions recommandées.
- **Validation humaine** : import CV et questionnaire produisent un `draft`
  non enregistré ; l'enregistrement passe par `PUT /api/profile`.
- **Traçabilité (§51)** : chaque offre garde `source.name`, `source.url` et
  `published_at` ; les tendances marché sont calculées sur ces données.
- **Expériences informelles** reconnues (§5bis.1) : types
  `informal | freelance | volunteer | apprenticeship | project`.
- Interface en **français**.

## Configuration (variables d'environnement)

| Variable          | Défaut                        | Rôle                        |
|-------------------|-------------------------------|-----------------------------|
| `SECRET_KEY`      | `dev-secret-change-me`        | signature JWT               |
| `DATABASE_URL`    | `sqlite:///.../skilljob.db`   | base de données             |
| `LLM_PROVIDER`    | `rules`                       | `rules` ou `openai`         |
| `LLM_API_KEY`     | vide                          | clé API OpenAI-compatible   |
| `LLM_BASE_URL`    | `https://api.openai.com/v1`   | endpoint LLM                |
| `LLM_MODEL`       | `gpt-4o-mini`                 | modèle LLM                  |

L'assistant fonctionne sans LLM (moteur par règles ancré sur les données
réelles). Si `LLM_API_KEY` est fourni, il bascule sur un appel
OpenAI-compatible ; en cas d'erreur, retour automatique aux règles.

## Export PDF

L'export des documents (`GET /api/documents/{id}/export?format=pdf`) nécessite
`reportlab` (dépendance optionnelle, import protégé). Sans reportlab, le
markdown est retourné (conformité contrat §7).

```bash
pip install reportlab   # optionnel
```
