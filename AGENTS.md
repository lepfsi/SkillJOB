# AGENTS.md — Guide pour les agents IA travaillant sur ce dépôt

## Projet

OrientSkill AI — plateforme d'intelligence professionnelle pour jeunes
Camerounais (MVP concours MINJEC). Référentiel fonctionnel maître :
`projet_ia_minjec_formalisation-1.md` à la racine. Contrat d'API strict :
`docs/API_CONTRACT.md` — **ne jamais s'en écarter** sans mettre à jour les
deux côtés (backend `schemas.py` + frontend).

## Stack

- **Backend** : Python / FastAPI, SQLAlchemy 2 (SQLite `backend/skilljob.db`),
  Pydantic v2, PyJWT, pypdf. venv dans `backend/.venv`.
- **Frontend** : React 18 + Vite + react-router-dom v6, JavaScript seul
  (pas de TypeScript), un seul fichier CSS (`src/styles.css`), aucune
  librairie UI supplémentaire.

## Commandes de vérification (OBLIGATOIRES avant de terminer une tâche)

```bash
# Backend — tous les tests doivent passer
cd backend && source .venv/Scripts/activate
python -m pytest tests -q

# Backend — démarrage
python -m uvicorn app.main:app --port 8000 --reload

# Frontend — le build doit passer sans erreur
cd frontend
npm run build
npm run dev   # port 5173, proxy /api -> localhost:8000

# Vérification HTTP isolée (ne touche JAMAIS la base de l'utilisateur)
bash scripts/smoke.sh   # base .smoke/ jetable, port 8123
```

**RÈGLES ABSOLUES de vérification :**
- NE JAMAIS supprimer `backend/skilljob.db` (données réelles des utilisateurs).
- NE JAMAIS faire de `taskkill //IM python.exe` global : l'utilisateur a peut-être
  son serveur en cours. Toujours arrêter par PID le process démarré par l'agent.
- Les vérifications HTTP passent par `bash scripts/smoke.sh` : base SQLite isolée
  (`DATABASE_URL` dédié), port séparé, nettoyage de `.smoke/` uniquement.

Compte démo : `demo@orientskill.cm / demo1234` (candidat) ·
`recruteur@orientskill.cm / recruteur1234` (recruteur) ·
`admin@orientskill.cm / admin1234` (admin).

## Règles métier inviolables (du cahier des charges)

1. **Pas d'invention** (§47) : CV ciblé, lettre, entretien — uniquement à
   partir du profil validé. Ne jamais inventer diplôme, expérience,
   certification, compétence, employeur.
2. **Score explicable** (§12) : chaque match inclut covered/partial/missing,
   strengths, explication FR, recommended_actions. Jamais un simple pourcentage.
3. **Validation humaine** : import CV / questionnaire produisent un brouillon
   (`draft`) NON persisté ; seul `PUT /api/profile` enregistre.
4. **Traçabilité des offres** (§51) : source + URL + published_at toujours conservés.
5. **Expériences informelles** (§5bis) : elles comptent dans le matching.
   « Absence d'information ≠ absence de compétence » (§48).
6. Interface et réponses **100 % en français**.
7. Symboles de match imposés : ✓ couverte · △ partielle · ○ manquante.

## Conventions

- Backend : commentaires sobres en français, docstrings courts, services purs
  dans `app/services/` (testables sans HTTP), routes fines dans `app/api/`.
- Frontend : labels FR, pas d'emojis, `src/lib.js` pour helpers/libellés partagés,
  composants réutilisables dans `src/components/` (ProfileEditor partagé entre
  DraftReview et Profile).
- Seed auto au démarrage si la table users est vide (`app/main.py::seed_database`) ;
  les données de référence vivent dans `backend/data/*.json`.
- Ne pas committer `backend/skilljob.db` ni `frontend/node_modules`/`dist`.

## Liens assistant frontend → routes

L'assistant backend renvoie des href backend (`/jobs/3`, `/profile`…) ;
le frontend les traduit via `mapInternalPath()` dans `src/lib.js`.
Si une route frontend change, mettre à jour cette fonction.
