# OrientSkill AI — Frontend

Frontend du MVP "OrientSkill AI", plateforme d'intelligence professionnelle pour les jeunes Camerounais.

## Stack

- Vite + React 18 + react-router-dom v6 (JavaScript)
- CSS maison unique (`src/styles.css`), mobile-first
- Proxy `/api` → `http://localhost:8000` (backend FastAPI)

## Lancement

```bash
npm install
npm run dev
```

Application disponible sur http://localhost:5173 (le backend doit tourner sur http://localhost:8000).

## Build de production

```bash
npm run build
npm run preview
```

## Structure

- `src/api/client.js` — wrapper fetch (Bearer JWT depuis `localStorage` clé `orientskill_token`, redirect login sur 401)
- `src/context/AuthContext.jsx` — login / register / logout / utilisateur courant
- `src/components/` — Layout, MatchBadge, SkillTag, éléments communs
- `src/pages/` — Login, Register, Onboarding, Questionnaire, DraftReview, Dashboard, Inbox, Opportunities, OpportunityDetail, Applications, Career, Skills, Learning, Documents, Profile, Assistant

Le contrat d'API suivi est décrit dans `../docs/API_CONTRACT.md`.
