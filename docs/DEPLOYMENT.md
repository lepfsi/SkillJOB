# Déploiement Vercel (frontend) + Render (backend)

URLs de production :
- Frontend : https://skill-job-iota.vercel.app
- Backend : https://skilljob.onrender.com (docs : `/docs`)

## 1. Communication frontend → backend : déjà en place

Le frontend appelle des chemins relatifs `/api/...`. Le fichier
`frontend/vercel.json` contient un **rewrite** :

```json
{
  "rewrites": [
    { "source": "/api/(.*)", "destination": "https://skilljob.onrender.com/api/$1" }
  ]
}
```

Concrètement : le navigateur appelle `https://skill-job-iota.vercel.app/api/...`,
et **Vercel transmet la requête à Render côté serveur**. Avantages :

- **aucun code frontend à changer** (les chemins restent relatifs) ;
- **pas de CORS** : le navigateur ne voit qu'une seule origine ;
- gratuit (les rewrites sont proxysés par Vercel).

**À faire :** committer `frontend/vercel.json` et redéployer Vercel
(push sur la branche connectée, ou « Redeploy » dans le dashboard).

Mode alternatif (non nécessaire) : définir `VITE_API_URL=https://skilljob.onrender.com`
dans les variables d'environnement Vercel — le client appelle alors Render
en direct (CORS requis, voir §3).

## 2. Render : variables d'environnement OBLIGATOIRES

Dashboard Render → service backend → **Environment** :

| Variable | Valeur | Pourquoi |
|---|---|---|
| `SECRET_KEY` | une longue chaîne aléatoire (`openssl rand -hex 32`) | Sans elle, les JWT sont signés avec la clé de dev présente dans le code → n'importe qui peut forger des jetons |
| `DATABASE_URL` | URL PostgreSQL Render (voir §4) | **Sans elle, SQLite est utilisé sur un disque ÉPHÉMÈRE : toutes les données (comptes, offres importées, candidatures) sont effacées à chaque déploiement ou redémarrage** |
| `CORS_ORIGINS` | `https://skill-job-iota.vercel.app` | Ceinture de sécurité si un appel direct à Render est tenté (le rewrite Vercel rend le CORS inutile en usage normal) |
| `CORS_ORIGINS` en dev | ajouter `,http://localhost:5173` | Pour continuer à développer en local contre le Render |

## 3. Base de données : PostgreSQL Render (recommandé, gratuit)

Le disque du free tier Render est **éphémère** : chaque déploiement ou
redémarrage remet à zéro le système de fichiers, donc `skilljob.db`
disparaît. Deux options :

- **PostgreSQL Render (recommandé, offre gratuite)** : Render → « New » →
  « PostgreSQL » → copier l'« Internal Database URL », puis la définir
  comme `DATABASE_URL` sur le service backend et redéployer. Le code est
  **déjà compatible Postgres** (SQLAlchemy portable, `check_same_thread`
  uniquement pour SQLite, migration `_ensure_columns` en SQL standard) ;
  les tables et le seed (comptes démo, offres, taxonomie) se créent
  automatiquement au premier démarrage.
- **Render Persistent Disk** (payant, ~$7/mois) : garde SQLite, disque
  monté sur `/opt/render/project/src/backend/data` → définir
  `DATABASE_URL=sqlite:////opt/render/project/src/backend/data/skilljob.db`.

## 4. Démarrage du backend sur Render

Render → service → Settings :
- **Build Command** : `pip install -r requirements.txt`
- **Start Command** : `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  (Render fournit `$PORT` automatiquement)

## 5. Réveil du free tier (« cold start »)

Render free s'endort après ~15 min d'inactivité : la **première requête
prend 30 à 50 s** (constaté : 44 s sur notre instance), ensuite tout est
rapide (1,2 s). Pour un concours, deux options :
- payer une instance (à partir de ~$7/mois, toujours active) ;
- ou un ping automatique gratuit (UptimeRobot, cron-job.org) toutes les
  10 min sur `https://skilljob.onrender.com/api/health`.

## 6. Checklist finale

- [ ] `frontend/vercel.json` committé + Vercel redéployé
- [ ] Render : `SECRET_KEY` défini
- [ ] Render : `DATABASE_URL` PostgreSQL créé et défini
- [ ] Render : `CORS_ORIGINS=https://skill-job-iota.vercel.app`
- [ ] Test : ouvrir https://skill-job-iota.vercel.app/login, se connecter
  avec `demo@orientskill.cm / demo1234`
- [ ] Test chat assistant : le bandeau « Modèle connecté » exige la clé
  LLM re-saisie dans `/admin/parametres` (les variables d'environnement
  `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` sur Render fonctionnent aussi)
