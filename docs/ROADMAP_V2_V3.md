# OrientSkill AI — Feuille de route V2 / V3

**Document de formalisation des évolutions post-MVP.**
Référentiel maître : `projet_ia_minjec_formalisation-1.md` (ci-après « le cahier des charges »).
État de départ : MVP V1 livré (profil intelligent, extraction CV/questionnaire, matching
explicable, base d'offres locale, CV ciblé/lettre, assistant, dashboard — §55).
Le présent document formalise les modules réservés à l'évolution (§55-57, §76).
Document de conception uniquement : aucun engagement d'implémentation.

## 1. Tableau de phases

| Phase | Périmètre | Modules | Principes directeurs |
|---|---|---|---|
| V2 — Élargissement opérationnel | Collecte automatisée multi-source ; connecteur LinkedIn autorisé ; espace recruteur complet ; canaux WhatsApp/Telegram (notifications puis conversation) | 1, 2, 3, 4 | Connecter la plateforme au marché réel ; ouvrir le côté demande ; accès 100 % via mécanismes autorisés (§67) |
| V3 — Infrastructure d'intelligence | Skill Graph national ; vérification de credentials ; données institutionnelles à grande échelle | 5, 6, 7 | Devenir une infrastructure d'intelligence emploi-compétences (§72) ; ancrage national ; gouvernance renforcée |

Règle de dépendance : aucun module V3 ne démarre tant que les critères d'acceptation des
modules 2 et 3 ne sont pas atteints (le Skill Graph et le dashboard institutionnel consomment
leurs données).

## 2. Matrice de risques globale

| # | Risque | Modules | Gravité | Prob. | Mitigation |
|---|---|---|---|---|---|
| R1 | Accès refusé/restreint aux API externes (LinkedIn, agrégateurs) | 1, 2 | Élevée | Élevée | Connecteurs interchangeables (§77) ; aucune dépendance exclusive (§10) ; mode dégradé sans LinkedIn |
| R2 | Non-conformité aux CGU d'une plateforme tierce | 1, 2, 4 | Élevée | Moyenne | Revue juridique par connecteur ; API officielles et partner programs uniquement ; scraping interdit (§67) |
| R3 | Exposition de données personnelles des jeunes | 3, 4, 6, 7 | Critique | Moyenne | Privacy by Design (§45-46) ; consentement par finalité ; minimisation ; visibilité contrôlée par le candidat |
| R4 | Non-conformité loi de protection des données (n° 2010/012, RGPD-like) | 4, 6, 7 | Critique | Moyenne | Registre des traitements ; durées de conservation ; droits d'accès/suppression ; référent données avant V3 |
| R5 | Qualité des offres (doublons, expirées, fraudes) | 1, 2, 5 | Moyenne | Élevée | Déduplication ; scoring fraîcheur/fiabilité (§51) ; date de dernière vérification |
| R6 | Biais de matching amplifié côté recruteur | 3, 7 | Élevée | Moyenne | Explicabilité (§12) ; monitoring des biais (§48) ; pas de filtre âge/genre/origine |
| R7 | Surcharge informationnelle (notifications) | 4 | Moyenne | Élevée | Filtre pertinence+fraîcheur+urgence (§52) ; quota ; opt-out en un mot-clé |
| R8 | Coût/dépendance à un agrégateur WhatsApp | 4 | Moyenne | Élevée | Canal web complet et gratuit ; WhatsApp/Telegram en complément ; plafond budgétaire |
| R9 | Partenaires de vérification indisponibles/coûteux | 6 | Moyenne | Élevée | Attestation en couches ; badge optionnel, jamais requis pour candidater |
| R10 | Ré-identification via agrégats institutionnels | 7 | Critique | Faible | k-anonymat >= 10 ; suppression identifiants ; revue avant publication |
| R11 | Dérive « boîte noire » des recommandations V3 | 5, 6, 7 | Élevée | Moyenne | Explicabilité obligatoire (§47) ; audits ; contrôle humain préservé |
| R12 | Coût infrastructure (graphe, ingestion, LLM) | 2, 5, 7 | Moyenne | Moyenne | Priorisation modulaire ; ingestion incrémentale ; modèles locaux si qualité suffisante |

## 3. Module 1 — Connecteur LinkedIn

### 3.1 Objectif fonctionnel
Collecter des offres et suivre des pages carrière via les mécanismes autorisés uniquement :
API officielles (Jobs API, Talent APIs), partner programs, flux explicitement prévus à cet
effet. Aucune architecture ne doit supposer un scraping contraire aux CGU (§10, §67).
Le connecteur enrichit la base existante et n'est jamais une dépendance unique.

### 3.2 Architecture technique
Connecteur derrière l'interface générique du module 2 (contrat `JobSourceConnector`),
activable par configuration. OAuth 2.0, jetons chiffrés, rotation automatique.
Worker d'ingestion asynchrone respectant les rate limits documentées, backoff
exponentiel. Mode dégradé : connecteur inactif = service fonctionnel sur les autres
sources — critère d'acceptation.

### 3.3 Modèle de données / API indicatifs
```text
linkedin_account : id, org_id, client_id, token_encrypted, token_expires_at, scopes, status
linkedin_company_watch : id, company_linkedin_id, company_name, last_synced_at
```
Les offres LinkedIn réutilisent le modèle `Job` (§51 : source, source_url, published_at,
collected_at, last_verified_at). API : `POST /api/admin/connectors/linkedin/sync`,
`GET /api/jobs?source=linkedin`. Aucun endpoint n'expose de contenu LinkedIn au-delà
des champs normalisés et attribués.

### 3.4 Dépendances et prérequis
Approbation d'une application LinkedIn (et contrat partner si applicable) ; avis juridique
écrit sur le périmètre de collecte/conservation ; module 2 opérationnel.

### 3.5 Conformité / risques
ToS LinkedIn strictement respectées : aucune collecte hors API, pas de revente,
attribution systématique. Aucune donnée de profil LinkedIn d'individus collectée.
Risques R1, R2 — mitigés par le mode dégradé et l'audit de code.

### 3.6 Phase et critères d'acceptation — V2
1. 100 % des offres LinkedIn en base ont source, URL, dates publication/collecte.
2. Taux d'erreur d'ingestion < 2 % sur 30 jours ; zéro violation de rate limit non gérée.
3. Désactivation testée sans interruption de service.
4. Zéro requête réseau vers LinkedIn hors API officielle (audit de code).

## 4. Module 2 — Collecte multi-source automatisée

### 4.1 Objectif fonctionnel
Industrialiser la collecte : APIs partenaires, sites carrière, flux RSS, partenaires
institutionnels (§50). Pipeline ingestion → normalisation → déduplication → scoring de
fraîcheur et de fiabilité source (§51) → indexation pour le matching V1. La même offre
multi-diffusée est fusionnée en une entrée unique avec historique des sources.

### 4.2 Architecture technique
```text
SOURCES → CONNECTEURS (plugin isolé par source, testable sans réseau)
  → INGESTION QUEUE (worker asynchrone planifié)
  → NORMALIZER (schéma canonique Job, mapping par source)
  → DEDUPLICATOR (empreinte titre+entreprise+localisation ; similarité textuelle)
  → SCORING (fraîcheur : âge + dernière vérification ; fiabilité : historique source)
  → BASE D'OFFRES → MATCHING V1
```
Statuts d'offre : active / expirée présumée / vérifiée / signalée. Tableau de bord
d'observabilité interne : volume par source, taux de doublons, âge médian.

### 4.3 Modèle de données / API indicatifs
```text
source : id, name, type (api|rss|career_site|partner), reliability_score,
         config_encrypted, rate_limit, enabled, last_run_at, last_run_status
job_source_ref : job_id, source_id, external_id, url, collected_at
job (extensions) : freshness_score, reliability_score, dedup_key, status, last_verified_at
```
API : `POST /api/admin/sources`, `POST /api/admin/sources/{id}/run`,
`GET /api/admin/sources/{id}/stats`. API jeune inchangée (contrat docs/API_CONTRACT.md).

### 4.4 Dépendances et prérequis
Orchestrateur de tâches ; secrets chiffrés ; jeu de données multi-sources pour la
déduplication. Le pipeline doit fonctionner sans LinkedIn (aucune dépendance module 1).

### 4.5 Conformité / risques
Chaque source documentée : base légale, CGU, fréquence autorisée. Offres frauduleuses :
scoring + signalement + retrait manuel. Risques R1, R5.

### 4.6 Phase et critères d'acceptation — V2
1. Au moins 3 sources distinctes en production dont 1 API et 1 flux RSS.
2. Doublons résiduels < 5 % (audit manuel de 100 offres).
3. 100 % des offres avec source, URL originale, 3 dates (§51).
4. Offres non vérifiées depuis 30 jours marquées automatiquement « à vérifier ».
5. Base active >= 200 offres camerounaises de moins de 60 jours.

## 5. Module 3 — Espace recruteur complet

### 5.1 Objectif fonctionnel
Ouvrir le côté demande (§20-21, §60) : compte entreprise, publication d'offres,
structuration IA des exigences (compétences extraites et normalisées), talent search par
compétences, shortlists, suivi des candidatures, contact uniquement via mécanismes
autorisés, matching recruteur↔talent explicable (✓ / △ / ○, §12).

### 5.2 Architecture technique
Rôle applicatif `recruiter` distinct (séparation des accès, §45). Réutilisation du moteur
de matching V1 en mode inverse : le besoin est encodé dans le même format qu'une offre,
aucune duplication de logique. Index de talents pré-calculé (compétences normalisées,
localisation, disponibilité, visibilité consentie). Notification au jeune sur intérêt
recruteur (opt-in).

### 5.3 Modèle de données / API indicatifs
```text
company : id, name, sector, website, verified (validation manuelle)
recruiter_user : user_id, company_id, role (owner|member), status
recruiter_job (extension de job) : company_id, created_by, requirements_raw,
              requirements_structured (JSON), status (draft|published|closed)
shortlist : id, recruiter_user_id, recruiter_job_id, name, created_at
shortlist_entry : shortlist_id, target_user_id, match_summary, added_at
recruiter_application : id, recruiter_job_id, target_user_id,
              status (new|shortlisted|interview|offer|hired|rejected), timeline
```
API : `POST /api/recruiter/jobs`, `POST /api/recruiter/jobs/{id}/structure`,
`POST /api/recruiter/talent-search`, `POST /api/recruiter/shortlists`,
`PATCH /api/recruiter/applications/{id}`. Le candidat voit toute candidature recruteur
dans son mini-ATS V1.

### 5.4 Dépendances et prérequis
Module 2 (offres fraîches structurées) ; profils complétés + confidentialité granulaire ;
process léger de vérification des entreprises (anti-offres frauduleuses).

### 5.5 Conformité / risques
Visibilité des profils strictement subordonnée au consentement du jeune (§22, §46) ;
défaut = invisible ; éléments masquables. Recherche excluant par conception tout critère
sensible (âge, genre, origine, établissement — §48). Contact par messagerie interne
uniquement ; jamais de revente de coordonnées. Risques R3, R6.

### 5.6 Phase et critères d'acceptation — V2
1. 20 entreprises vérifiées dont 10 ayant publié 1 offre structurée par l'IA.
2. Talent search : précision@10 >= 70 % sur un jeu d'évaluation (jugement humain).
3. 100 % des matchs recruteur affichent covered/partial/missing + explication (§12).
4. 100 % des profils contactables avec consentement de visibilité actif et horodaté.
5. Zéro critère sensible utilisable comme filtre (test automatisé).

## 6. Module 4 — Canaux WhatsApp / Telegram

### 6.1 Objectif fonctionnel
Atteindre les jeunes sur leurs canaux quotidiens (§25, §25bis) via API officielles
uniquement : WhatsApp Business API via agrégateur (BSP), Telegram Bot API. Deux niveaux :
(a) notifications intelligentes (offres fortement compatibles, échéances, recruteur
intéressé) ; (b) conversation avec l'assistant (questions courtes, réponses au diagnostic,
suivi du parcours).

### 6.2 Architecture technique
Service de notification central : événement métier → filtrage (§52 : pertinence +
fraîcheur + compatibilité + préférences + urgence) → sélecteur de canal (in-app, email,
WhatsApp, Telegram). Adaptateurs derrière une interface commune `NotificationChannel` ;
templates WhatsApp pré-approuvés ; Telegram via Bot API. Niveau conversationnel : pont
vers le service assistant V1, réponses courtes + lien web. Opt-out immédiat par
mot-clé (STOP) ; réactivation uniquement dans l'application.

### 6.3 Modèle de données / API indicatifs
```text
channel_subscription : user_id, channel (whatsapp|telegram), handle (chiffré),
    consent_at, consent_scope (notifications|conversation), status, opted_out_at
notification_log : user_id, event_type, channel, sent_at, delivered, template_id
channel_message_in : id, user_id, channel, direction (in|out), payload_hash, created_at
```
API : `PUT /api/me/channels` (préférences/consentement), `POST /api/webhooks/whatsapp`,
`POST /api/webhooks/telegram` (webhooks signés). Templates versionnés et journalisés.

### 6.4 Dépendances et prérequis
Compte WhatsApp Business via BSP + modèles approuvés ; bot Telegram + webhook sécurisé ;
budget messagerie plafonné et suivi (R8).

### 6.5 Conformité / risques
Consentement explicite, séparé, horodaté par canal et par finalité ; opt-out en un
message, effectif immédiat. Numéros : minimisation, chiffrement au repos, jamais partagés.
WhatsApp ToS : respect des templates et de la fenêtre de service 24 h ; aucun message
promotionnel hors template. Risques R3, R4, R7, R8.

### 6.6 Phase et critères d'acceptation — V2 (notifications), V2.5 (conversationnel)
1. 100 % des messages avec consentement actif horodaté au moment de l'envoi.
2. Opt-out traité en < 5 minutes ; zéro message après opt-out (test automatisé).
3. Taux de livraison >= 95 % sur 30 jours.
4. Maximum 5 notifications push par utilisateur et par semaine (filtre §52).
5. Conversationnel : 80 % des conversations sans collecte de donnée personnelle
   nouvelle sans re-validation web.

## 7. Module 5 — Skill Graph national

### 7.1 Objectif fonctionnel
Construire le graphe métiers ↔ compétences ↔ formations ↔ offres ↔ talents (§40-41).
Cas d'usage : trajectoires professionnelles réalistes (§33), détection de compétences
émergentes sur le marché camerounais, recommandation de formations fondée sur les écarts,
identification de compétences rares, trajectoires proposées même sans titre exact (§41).

### 7.2 Architecture technique
Base graphe dédiée (Neo4j ou équivalent) alimentée par ETL nocturne batch depuis les
données relationnelles V1/V2 (Skill, Occupation, Job/UserSkill, formations). Pas de
dépendance temps réel pour les parcours critiques. Services de lecture : trajectoires
(plus court chemin pondéré), compétences émergentes (séries temporelles de fréquences
dans les offres), similarité de compétences (co-occurrence). Toute recommandation passe
par la couche d'explicabilité existante : le graphe fournit des chemins, l'interface des
justifications (§47).

### 7.3 Modèle de données / API indicatifs
```text
Nœuds : Skill, Occupation, Formation, Offer, Talent (pseudonymisé)
Arêtes :
  (Skill)-[:REQUIRED_IN {importance, trend}]->(Offer)
  (Occupation)-[:REQUIRES {weight}]->(Skill)
  (Skill)-[:RELATED_TO {similarity}]->(Skill)
  (Formation)-[:TEACHES {coverage}]->(Skill)
  (Occupation)-[:PATH_TO {gap_count}]->(Occupation)
```
API : `GET /api/career/paths?from=...&to=...`, `GET /api/market/emerging-skills`,
`GET /api/skills/{id}/related`. Les nœuds Talent ne sont jamais exposés : seuls des
agrégats anonymisés alimentent les endpoints market.

### 7.4 Dépendances et prérequis
Critères des modules 2 et 3 atteints (sinon graphe trop pauvre) ; taxonomie de
compétences consolidée et versionnée (extension du référentiel V1) ; hébergement,
sauvegardes, sauvegarde/restauration testée.

### 7.5 Conformité / risques
Nœuds Talent construits uniquement depuis des profils consentants, pseudonymisés, jamais
exposés. Chaque trajectoire recommandée liste les compétences de chaque pas du chemin.
Tendances toujours fondées sur des données identifiables et datées (§5bis.2). Risques
R11, R12.

### 7.6 Phase et critères d'acceptation — V3
1. Graphe couvrant >= 150 compétences, >= 40 métiers, >= 500 offres historisées.
2. Pertinence des trajectoires >= 70 % sur 30 cas évalués par des experts métier.
3. Liste mensuelle de compétences émergentes avec volume d'appui daté, jamais
   d'affirmation générique.
4. 100 % des réponses de trajectoire incluent compétences manquantes + formations.
5. Temps de réponse des endpoints graphe < 2 s au 95e percentile.

## 8. Module 6 — Vérification de credentials

### 8.1 Objectif fonctionnel
Passer d'un CV déclaratif à un profil fondé sur les preuves (§23-24) : vérification des
diplômes et certifications avec partenaires habilités, badges numériques de compétences
(Open Badges ou équivalent), attestation d'expériences par références. Chaque vérification
requiert le consentement explicite de l'utilisateur et reste optionnelle : aucun jeune
n'est pénalisé pour un credential non vérifiable.

### 8.2 Architecture technique
Couche d'attestation à niveaux de confiance croissants : (1) déclaré (statut V1) ;
(2) attesté par un tiers de confiance (référence professionnelle) ; (3) vérifié auprès
d'un partenaire habilité ; (4) badge numérique signé (JSON + signature). Connecteurs de
vérification par partenaire (API si disponible, sinon circuit assisté : pièce
justificative + revue manuelle journalisée). La vérification enrichit le niveau de
confiance affiché ; le matching pondère mais n'exclut jamais sur la seule absence de
preuve (§48).

### 8.3 Modèle de données / API indicatifs
```text
credential : id, user_id, type (degree|certification|experience_reference), issuer,
    issued_at, verification_status (declared|attested|verified|expired),
    evidence_url, verified_by, verified_at
credential_request : id, user_id, credential_id, partner_id, consent_at, status, expires_at
badge : id, user_id, skill_id, credential_id, issued_at, badge_json_url, signature, revoked
```
API : `POST /api/me/credentials`, `POST /api/me/credentials/{id}/request-verification`
(consentement horodaté, durée de délégation fixée), `GET /api/me/badges`,
`GET /api/badges/{id}/verify` (public, par signature).

### 8.4 Dépendances et prérequis
Au moins 2 conventions signées avec des partenaires habilités (1 établissement
d'enseignement, 1 organisme de certification) avant activation du niveau 3 ;
infrastructure de signature et de révocation.

### 8.5 Conformité / risques
Consentement distinct, limité dans le temps, révocable ; le partenaire ne reçoit que le
strict nécessaire (minimisation). Justificatifs sensibles : chiffrement au repos, accès
journalisé, durée de conservation définie. Le badge valorise sans jamais stigmatiser
l'absence de preuve. Risques R3, R4, R9.

### 8.6 Phase et critères d'acceptation — V3
1. Au moins 2 conventions de vérification opérationnelles.
2. 100 % des vérifications avec consentement horodaté, spécifique, révocable.
3. 100 % des badges vérifiables publiquement par signature ; révocation testée.
4. Non-régression : le matching fonctionne pour les profils sans credential vérifié.
5. Délai moyen consentement → résultat < 10 jours ouvrés, documenté.

## 9. Module 7 — Données institutionnelles à grande échelle

### 9.1 Objectif fonctionnel
Fournir aux institutions (MINJEC, structures d'accompagnement — §39, §61) un dashboard
agrégé et anonymisé : jeunes inscrits/actifs, compétences disponibles vs demandées,
écarts par secteur et région, tendances du marché, formations suivies, candidatures et
placements lorsque mesurables. Répondre à la question de niveau 4 (§72) : « où se
trouvent les écarts de compétences ? ».

### 9.2 Architecture technique
Entrepôt analytique distinct (ETL nocturne depuis la base opérationnelle), séparant
données personnelles et analytiques (§46). Moteur d'anonymisation : agrégation avec seuil
de k-anonymat (>= 10 individus par cellule publiée), suppression des identifiants,
généralisation (tranches d'âge, régions plutôt que villes). Rôles institutionnels à accès
restreint, MFA obligatoire (§45), journalisation intégrale des consultations. Exports
CSV/JSON soumis à la même anonymisation.

### 9.3 Modèle de données / API indicatifs
```text
agg_cohort_daily : date, region, sector, age_band, active_users
agg_skill_gap : period, sector, skill_id, demand_count, supply_count, gap_index
agg_market_trend : period, sector, occupation_id, offer_count
institutional_user : user_id, institution, role (analyst|admin), mfa_enabled
access_audit : institutional_user_id, indicator_viewed, filters, viewed_at
```
API : `GET /api/institution/indicators?name=...&sector=...&period=...` (agrégats
k-anonymisés uniquement), `POST /api/institution/exports` (approbation admin requise).
Aucun filtre ne doit pouvoir descendre jusqu'à l'individu.

### 9.4 Dépendances et prérequis
Modules 2 et 3 en production + volume d'utilisateurs suffisant pour dépasser les seuils
d'anonymat ; convention cadre avec l'institution consommatrice ; référent protection des
données désigné (§45).

### 9.5 Conformité / risques
Finalité statistique et programmatique uniquement ; ré-identification contractuellement
interdite et techniquement filtrée. Genre, âge et localisation présents dans les agrégats
uniquement pour l'analyse d'équité (§48), sous accès restreint et journalisé. Droit
d'opposition des jeunes aux exports institutionnels, sans perte de fonctionnalités.
Risques R3, R4, R10.

### 9.6 Phase et critères d'acceptation — V3
1. 100 % des cellules publiées respectent k-anonymat >= 10 (test automatisé).
2. 100 % des consultations journalisées (utilisateur, filtre, horodatage).
3. Au moins 6 familles d'indicateurs exposées : inscrits/actifs, compétences
   disponibles, compétences demandées, écarts, tendances, candidatures/placements.
4. Requête aboutissant à < 10 individus : refusée (test automatisé).
5. Convention cadre signée avec au moins 1 institution avant ouverture des accès.

## 10. Prochaines actions concrètes recommandées

1. **Construire le socle d'ingestion et le dossier LinkedIn (modules 2 puis 1).**
   Implémenter le pipeline ingestion/normalisation/déduplication avec 3 sources non-LinkedIn
   (2 sites carrière camerounais + 1 flux RSS) — le connecteur LinkedIn s'y branchera tel
   quel. En parallèle, déposer la demande d'application LinkedIn et obtenir l'avis juridique
   écrit sur le périmètre de collecte autorisé.
2. **Prototyper l'espace recruteur sur un pilote restreint (module 3).** Recruter 5
   entreprises pilotes (réseau MINJEC), implémenter publication + structuration IA + talent
   search + shortlists, mesurer la précision du talent search sur des besoins réels. C'est
   le module V2 à plus forte valeur démontrable et la dépendance majeure des modules V3.
3. **Formaliser la gouvernance des données avant tout canal externe.** Rédiger la
   politique de confidentialité et le registre des traitements, désigner un référent
   protection des données, spécifier les consentements granulaires (visibilité recruteur,
   WhatsApp/Telegram, vérifications, exports institutionnels). Cette gouvernance
   conditionne les modules 4, 6 et 7 et doit précéder tout envoi de message externe.
