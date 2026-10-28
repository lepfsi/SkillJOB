# Roadmap de traitement des retours produits

Date de revue : lundi 26 octobre 2026
Source : retours utilisateurs et tests terrain du 25 octobre 2026.
Statut : document de travail. Aucune de ces remarques n'est encore considérée comme validée avant la revue.

Avancement au 27 octobre 2026 : les points 1, 2, 3, 4, 5, 6, 7, 8, 9 et 10
sont implémentés et vérifiés. Les points 11, 12, 13 à 22 et 23 restent à
traiter. Le point 23 a été ajouté en priorité 0.

Nouveaux retours intégrés le 26 octobre 2026 : les points 13 à 23 complètent
cette feuille de route. Ils sont classés dans la priorité correspondante et
restent à traiter. La numérotation continue à la suite pour ne pas modifier les
points déjà suivis.

Nouveaux retours intégrés le 27 octobre 2026 : les points 24 à 34 sont ajoutés
en fin de document. Ils complètent les irritants produits observés après la
première série de correctifs.

## Objectif

Corriger les irritants de confiance, de compréhension et de pilotage avant d'élargir la plateforme. Les points ci-dessous sont classés par priorité produit, avec pour chacun :

- le constat observé,
- l'objectif cible,
- les actions de mise en oeuvre,
- les critères d'acceptation.

## Priorité 0 : confiance et cohérence du parcours

### 1. Décision de vérification de profil non notifiée

**Constat**
Quand l'administration valide ou refuse une demande de vérification, le candidat n'est pas informé du résultat ni du motif.

**Objectif**
Le candidat doit recevoir une notification claire indiquant si sa demande a été validée ou refusée, avec le motif quand il y en a un.

**Actions**
- Ajouter un événement de notification `verification_decision`.
- Enregistrer la date de décision et le motif côté utilisateur.
- Afficher la décision dans la rubrique Notifications avec le statut et le motif.
- Envoyer un e-mail uniquement si l'utilisateur a activé ce type d'alerte.

**Critères d'acceptation**
- Toute validation génère une notification de succès.
- Tout refus génère une notification avec le motif obligatoire.
- Le candidat voit la décision sans recharger la page.
- Le journal `notification_log` conserve une trace de l'envoi éventuel.

### 2. Notifications visibles avant la création du compte

Statut : implémenté et vérifié le 27 octobre 2026 (filtrage par date de
création du compte, côté offres et événements persistés).

**Constat**
Un nouvel utilisateur peut voir des notifications antérieures à la création de son compte.

**Objectif**
Aucun utilisateur ne doit recevoir des événements calculés avant son inscription.

**Actions**
- Auditer la construction de la boîte de notifications.
- Filtrer tous les événements sur la date de création du compte utilisateur.
- Vérifier le seed de démonstration et les données de test.
- Ajouter un test de non-régression sur un compte fraichement créé.

**Critères d'acceptation**
- Un nouveau compte ne voit aucune notification plus ancienne que sa date de création.
- Les notifications du compte de démonstration ne fuient pas vers les nouveaux comptes.

### 3. Recommandations « Excel » non explicables

Statut : implémenté et vérifié le 27 octobre 2026 (raison et source
affichées pour chaque écart de compétence).

**Constat**
Tous les profils semblent recevoir des recommandations liées à Excel. Il faut déterminer si c'est une vraie tendance de marché ou un artefact de seed.

**Objectif**
Chaque recommandation doit être explicable, personnalisée et traçable.

**Actions**
- Auditer le moteur de recommandation et les données de marché.
- Séparer les recommandations génériques des recommandations personnalisées.
- Ajouter la raison de chaque recommandation dans la réponse API.
- Afficher la source de la tendance : offres analysées, période, volume.

**Critères d'acceptation**
- Aucune recommandation n'apparait sans raison affichée.
- Les recommandations diffèrent selon les profils réels.
- Un compte sans lien avec Excel ne reçoit pas Excel en priorité.

### 13. Contrôle de l'agent sans paramètres réels

**Constat**
La page « Mon agent » affiche un bloc « Contrôle de votre agent », mais il ne
donne pas accès à un ensemble complet de réglages. Le choix du mode existe,
mais il n'est pas relié à des paramètres visibles de périmètre, de fréquence,
de canaux ou de validation. Dans les paramètres du compte, aucun bloc ne
reprend ces réglages.

**Objectif**
Faire du bloc « Contrôle de votre agent » un vrai centre de réglages, avec des
paramètres persistés, compréhensibles et réellement appliqués par l'agent.

**Actions**
- Définir les paramètres utiles : mode de travail, actions autorisées,
  fréquence de veille, canaux d'alerte et niveau de validation humaine.
- Ajouter un modèle et une API de préférences agent, distincts du mode actuel.
- Afficher un résumé des réglages actifs dans « Mon agent ».
- Relier chaque paramètre à un effet vérifiable dans le comportement de l'agent.
- Auditer les modes existants pour supprimer ceux qui n'ont pas d'effet réel.

**Critères d'acceptation**
- Le bloc affiche au moins le mode, le périmètre d'action et le niveau de
  validation.
- Chaque modification est enregistrée et conservée après rechargement.
- Un paramètre affiché sans effet est supprimé ou rendu explicite.
- Le candidat ne peut activer que les actions autorisées par son rôle.

Statut : implémenté et vérifié le 28 octobre 2026 (préférences persistées
`agent_prefs`, API `GET/PUT /api/agent/preferences`, filtrage réel des offres
par périmètre, fréquence appliquée au digest et aux alertes, actions bloquées
côté API et filtrées dans l'inbox, tests `test_v26_agent_prefs.py`).

### 14. Lien « Gérer les paramètres » sans réglages de mode

**Constat**
Le lien « Gérer les paramètres » du bloc « Contrôle de votre agent » renvoie
vers la page Paramètres, mais celle-ci ne contient aucun réglage relatif au
mode ou au comportement de l'agent. L'utilisateur arrive dans une zone sans
rapport avec le lien.

**Objectif**
Le lien doit mener directement à une section de paramètres qui contient les
réglages de l'agent, ou disparaître si ces réglages n'existent pas.

**Actions**
- Ajouter une section « Agent » dans les paramètres du compte.
- Y reprendre le mode, le périmètre, la fréquence et la validation.
- Faire pointer le lien vers cette section avec une ancre ou une route dédiée.
- Afficher un état vide explicite si un réglage n'est pas encore disponible.
- Vérifier le parcours sur les rôles candidat et recruteur.

**Critères d'acceptation**
- Le clic sur « Gérer les paramètres » affiche immédiatement les réglages de
  l'agent.
- La même valeur est visible dans « Mon agent » et dans les paramètres.
- Aucun lien ne mène à une zone sans réglage correspondant.
- Le parcours fonctionne sans rechargement manuel.

Statut : implémenté et vérifié le 28 octobre 2026 (lien
`/parametres-compte#agent`, même composant `AgentPreferencesForm` dans Mon
agent et dans les paramètres, défilement automatique vers le bloc, état vide
explicite pour les rôles recruteur et admin).

### 15. Statuts de candidature incohérents entre candidat, recruteur et admin

**Constat**
Pour une offre publiée par un recruteur, le candidat peut faire passer sa
candidature à « offre reçue » ou « en entretien ». Ces étapes devraient être
décidées par le recruteur ou l'admin. L'admin peut aussi modifier un statut
sans validation préalable, ce qui crée des décisions contradictoires.

**Objectif**
Définir une machine à états unique et des permissions claires pour chaque rôle.

**Actions**
- Documenter les statuts et les transitions autorisées par rôle.
- Candidat : postuler, retirer sa candidature, décliner une offre, accepter une
  offre si le processus le prévoit.
- Recruteur : examiner, présélectionner, convoquer à un entretien, refuser,
  transmettre une offre.
- Admin : valider, corriger ou arbitrer une transition, avec motif et trace.
- Appliquer les règles côté API, pas seulement dans l'interface.
- Ajouter un journal des changements de statut avec auteur, date et motif.
- Mettre à jour les boutons et libellés côté candidat, recruteur et admin.

**Critères d'acceptation**
- Le candidat ne peut plus passer une candidature à « offre reçue » ou
  « en entretien ».
- Chaque transition est refusée par l'API si le rôle n'est pas autorisé.
- Le candidat peut décliner une offre et cette décision est visible par le
  recruteur et l'admin.
- Toute modification admin est tracée avec un motif.
- Les statuts affichés sont identiques dans les trois espaces.

Statut : implémenté et vérifié le 28 octobre 2026 (machine à états
`services/applications.py`, statuts `retiree` et `declinee`, transitions
candidat/recruteur/admin contrôlées côté API, arbitrage admin motivé et tracé,
timeline avec auteur et motif, tests `test_v26_application_workflow.py`).

### 16. Absence de page dédiée au traitement des recours

**Constat**
Les recours existent et peuvent être déposés, mais leur traitement est enfoui
dans la gestion des utilisateurs. L'admin n'a pas de page dédiée pour suivre,
instruire et décider les recours.

**Objectif**
Centraliser les recours dans un espace admin unique, avec statuts, historique
et décisions motivées.

**Actions**
- Ajouter une page « Recours » dans l'espace admin.
- Lister les recours avec filtres par statut, date, type et utilisateur.
- Afficher le contexte, le message du candidat et l'historique des échanges.
- Permettre d'accepter, refuser ou demander un complément, avec motif
  obligatoire.
- Notifier l'utilisateur de la décision et conserver une trace dans le journal.
- Afficher l'ancienneté des recours en attente.

**Critères d'acceptation**
- L'admin voit tous les recours ouverts dans une page dédiée.
- Chaque recours peut être instruit et clos avec une décision motivée.
- L'utilisateur reçoit une notification in-app et un e-mail si activé.
- Chaque décision est horodatée et traçable.
- Aucun recours ne reste sans statut après traitement.

Statut : implémenté et vérifié le 28 octobre 2026 (page admin dédiée
`/admin/recours`, filtres statut/type/utilisateur/texte/dates, contexte du
compte, ancienneté, fil d'historique, décisions accepter / refuser /
demander un complément avec motif obligatoire, notification in-app, e-mail
si le canal est activé, trace dans le journal admin, réponse du candidat
depuis l'écran de connexion).

### 23. Moteur d'alertes e-mail trop volumineux et redondant

Statut : à traiter (priorité 0 ajoutée le 27 octobre 2026).

**Constat**
Le moteur d'alertes envoie plusieurs fois la même offre par e-mail. Un
utilisateur a reçu 24 e-mails en 3 heures pour une seule offre correspondant à
50 % de son profil. Ce volume est ressenti comme du spam et peut faire fuir les
utilisateurs. Les causes probables sont un seuil d'envoi trop bas, l'absence de
déduplication par offre et des passes de digest répétées sur la même fenêtre.

**Objectif**
Envoyer un seul e-mail par offre réellement pertinente, avec un seuil supérieur
à 60 %, et conserver toutes les autres correspondances dans la zone
Notifications de l'application.

**Actions**
- Relever le seuil d'envoi e-mail à plus de 60 %. Les offres entre 45 % et
  60 % restent visibles in-app, sans e-mail.
- Dédupliquer les envois par utilisateur et par offre dans `notification_log`.
- Vérifier la déduplication avant chaque envoi et journaliser l'envoi réel.
- Remplacer les passes répétées par un digest quotidien unique ou par un envoi
  immédiat plafonné.
- Ajouter un plafond de fréquence, par exemple un e-mail d'alerte emploi par
  utilisateur et par jour.
- Rendre le planificateur idempotent : plusieurs exécutions sur la même
  période ne doivent pas renvoyer les mêmes offres.
- Conserver les notifications in-app pour toutes les correspondances à partir
  de 45 %.
- Ajouter un réglage de fréquence et de seuil dans les préférences e-mail.
- Ajouter des tests sur le seuil, la déduplication et le plafond de fréquence.
- Surveiller le volume d'e-mails par utilisateur et alerter en cas d'anomalie.

**Critères d'acceptation**
- Une offre à 50 % ne déclenche aucun e-mail mais reste dans la zone
  Notifications.
- Une offre à plus de 60 % déclenche au maximum un e-mail par utilisateur,
  même si le planificateur s'exécute plusieurs fois.
- Un utilisateur ne reçoit pas plus d'un e-mail d'alerte emploi par jour, sauf
  message critique de compte ou de sécurité.
- Toutes les correspondances restent consultables dans l'application.
- Les tests couvrent la déduplication et le seuil de 60 %.
- Aucun e-mail réel n'est envoyé pendant les vérifications.

## Priorité 1 : parcours candidat et recruteur

### 4. Iconographie du profil vérifié

Statut : implémenté et vérifié le 27 octobre 2026 (badge `VerifiedBadge`
harmonisé sur profil, dashboard et fiches candidat).

**Constat**
L'icône actuelle est trop ronde et manque de caractère.

**Objectif**
Obtenir un badge de vérification lisible, sobre et identifiable.

**Actions**
- Proposer deux nouvelles variantes graphiques.
- Rendre le badge responsive et accessible.
- Harmoniser l'icône entre profil public, dashboard et fiche candidat.

**Critères d'acceptation**
- Le badge est reconnaissable en 16 px.
- Il reste lisible sur fond clair et sombre.
- Le design final est validé par la direction produit.

### 5. Conversations empilées et réglages au bon endroit

**Constat**
Les réglages d'historique sont loin du fil visible et l'utilisateur ne peut gérer qu'une seule conversation. Il faut aussi pouvoir ouvrir plusieurs conversations séparées et les empiler.

**Objectif**
Avoir une pile de conversations à la manière des messages SMS, mais avec le design OrientSkill, et placer les réglages de chaque conversation directement dans son entete.

**Actions**
- Déplacer les boutons « éphémère » et « effacer » dans l'entete du fil de discussion.
- Ajouter un bouton « Nouvelle conversation ».
- Afficher les conversations précédentes empilées avec titre, date et dernier message.
- Permettre de fermer une conversation sans la supprimer.
- Permettre de rouvrir une conversation depuis la pile.

**Critères d'acceptation**
- Chaque conversation dispose de ses propres réglages.
- L'utilisateur peut créer autant de conversations qu'il veut.
- Les conversations s'empilent et restent distinguables.
- Une conversation fermée n'est pas rouverte automatiquement au rechargement.

### 6. Assistant de publication d'offre inopérant

Statut : implémenté et vérifié le 27 octobre 2026 (rédaction assistée avec
LLM et repli local, validation explicite avant application).

**Constat**
L'assistant de publication ne propose pas de mots ni de phrases pour préremplir les champs.

**Objectif**
Obtenir un vrai assistant de rédaction d'offre, utile dès la première phrase.

**Actions**
- Ajouter un mode « rédaction assistée » dans le formulaire recruteur.
- Générer intitulé, description, profil recherché et compétences à partir d'une description libre.
- Proposer des formulations prêtes à relire, jamais publiées sans validation.
- Afficher un bouton « Appliquer les suggestions » et un bouton « Ignorer ».

**Critères d'acceptation**
- Le recruteur obtient une proposition exploitable en moins de 5 secondes.
- Chaque champ suggéré reste modifiable.
- Aucune suggestion n'est enregistrée sans validation explicite.

### 7. Parcours d'entretien non ficelé

Statut : implémenté et vérifié le 27 octobre 2026 (parcours en trois étapes,
calendrier de créneaux, confirmation immédiate).

**Constat**
Les sous-pages Entretiens ne forment pas un parcours fluide, surtout pour répondre à une invitation.

**Objectif**
Créer un parcours unique et guidé pour accepter, refuser ou demander un autre créneau.

**Actions**
- Refondre la page Entretiens en trois étapes claires : invitation, réponse, confirmation.
- Ajouter un composant calendrier pour la sélection de créneau.
- Permettre d'ajouter un message d'accompagnement avant validation.
- Envoyer une confirmation immédiate au candidat et au recruteur.

**Critères d'acceptation**
- Le candidat ne quitte jamais la page pour répondre.
- Toute demande de créneau est accompagnée d'une proposition explicite.
- Le recruteur reçoit la demande dans un espace dédié, pas dans la messagerie générale.

### 8. Demande de changement de créneau coté recruteur

Statut : implémenté et vérifié le 27 octobre 2026 (file dédiée, historique
des propositions, notification du candidat à chaque décision).

**Constat**
Les demandes de créneau tombent dans la messagerie générale du recruteur, sans traitement dédié.

**Objectif**
Créer une file d'attente de négociation d'entretien.

**Actions**
- Ajouter une rubrique « Demandes de créneau » dans l'espace recruteur.
- Permettre d'accepter, refuser ou proposer un autre créneau.
- Conserver l'historique des propositions et réponses.
- Notifier le candidat à chaque décision.

**Critères d'acceptation**
- Le recruteur voit toutes les demandes de créneau en attente.
- Il peut répondre en une action sans passer par la messagerie.
- Le candidat reçoit la décision dans ses notifications et par e-mail si activé.

### 9. Prévisualisation d'une offre avant publication

Statut : implémenté et vérifié le 27 octobre 2026 (aperçu modal de la fiche
publique, publication bloquée sans aperçu).

**Constat**
Le bouton « Aperçu » coté recruteur n'ouvre pas un aperçu de l'offre en cours de rédaction.

**Objectif**
Le recruteur doit pouvoir relire l'offre telle qu'elle apparaîtra aux candidats avant de publier.

**Actions**
- Ajouter un état « brouillon » explicite.
- Créer un aperçu modal ou plein écran depuis le formulaire.
- Afficher le rendu final avec branding, photo, compétences et référence.
- Ajouter un bouton « Retour à la rédaction » sans perte de données.

**Critères d'acceptation**
- Aucune publication ne peut se faire sans aperçu disponible.
- L'aperçu reflète exactement la fiche publique.
- Le recruteur peut corriger et revoir l'aperçu autant de fois que nécessaire.

### 17. Sidebar de la page Notifications qui bloque le défilement

**Constat**
Sur la page Notifications, la sidebar ne s'arrête pas au niveau attendu. Elle
gêne le défilement du contenu et de la barre de défilement lorsque l'on
traverse l'en-tête.

**Objectif**
Rendre la sidebar stable et non bloquante, avec un défilement fluide du
contenu.

**Actions**
- Reproduire le problème sur desktop, tablette et mobile.
- Corriger la position sticky, la hauteur maximale et les débordements.
- Faire en sorte que la sidebar s'arrête avant le pied de page et ne recouvre
  jamais le contenu.
- Vérifier le comportement de la barre de défilement et du focus clavier.
- Ajouter une vérification visuelle aux largeurs 1280, 768 et 375 px.

**Critères d'acceptation**
- La page défile normalement avec la barre de défilement.
- La sidebar ne recouvre ni le titre ni le contenu.
- Le comportement est identique sur desktop et mobile.
- La navigation clavier reste possible.

Statut : implémenté et vérifié le 28 octobre 2026. Sur desktop, la
colonne est sticky sous la barre supérieure avec une hauteur maximale
et un défilement propre uniquement si son contenu dépasse la zone
visible. Sous 1000 px, elle reprend le flux normal, sans hauteur
contrainte ni défilement imbriqué. Vérification aux largeurs 1280, 768
et 375 px : aucun recouvrement du titre ni du contenu, page défilable
normalement, cartes de la colonne entièrement accessibles.

### 18. Préférences e-mail du candidat

**Constat**
Le candidat ne dispose pas de préférences claires pour choisir les
notifications qu'il reçoit par e-mail. Il peut donc recevoir tous les
événements dans sa boîte mail.

**Objectif**
Donner au candidat la maîtrise des e-mails qu'il reçoit, sans supprimer les
notifications importantes dans l'application.

**Actions**
- Ajouter une section « Notifications e-mail » dans les paramètres du candidat.
- Lister les catégories : nouvelles offres, offres expirantes, messages,
  candidatures, vérification et agent.
- Permettre d'activer ou désactiver chaque catégorie.
- Prévoir une fréquence immédiate ou un résumé quotidien pour les offres.
- Conserver l'envoi des messages critiques de compte et de sécurité.
- Appliquer les préférences dans le service de notification.
- Ajouter un lien de désabonnement dans les e-mails non critiques.

**Critères d'acceptation**
- Le candidat peut activer ou désactiver chaque catégorie.
- Une catégorie désactivée n'envoie aucun e-mail mais reste visible dans
  l'application.
- Les e-mails critiques de compte restent envoyés.
- Les préférences sont conservées après déconnexion.
- Aucun e-mail réel n'est envoyé pendant les tests.

Statut : implémenté et vérifié le 28 octobre 2026 (section « Notifications
e-mail » dans les paramètres, catalogue candidat, fréquence immédiate ou
quotidienne, plafond d'un e-mail d'offres par jour, déduplication par offre
dans `notification_log`, e-mails critiques toujours envoyés, lien de
désabonnement signé et testé sans envoi réel).

### 19. Paramètres e-mail spécifiques aux recruteurs et aux admins

**Constat**
La section « Quand souhaitez-vous un e-mail ? » des recruteurs et des admins
reprend les événements du candidat. Ces rôles n'ont pas les mêmes besoins et
ne peuvent pas choisir leurs propres alertes.

**Objectif**
Afficher à chaque rôle uniquement les événements qui le concernent.

**Actions**
- Définir un catalogue d'événements par rôle.
- Recruteur : nouvelle candidature, message de candidat, réponse à une
  invitation, offre publiée ou expirée, vérification d'entreprise.
- Admin : demande de vérification, recours, signalement, échec d'ingestion,
  alerte critique.
- Adapter l'API des préférences pour renvoyer les événements du rôle connecté.
- Rendre l'interface dynamique à partir de ce catalogue.
- Migrer les préférences existantes sans envoyer d'e-mails non demandés.

**Critères d'acceptation**
- Le recruteur ne voit que les événements recruteur.
- L'admin ne voit que les événements admin.
- Les événements candidat ne sont plus affichés à ces rôles.
- Chaque rôle peut activer ou désactiver ses alertes indépendamment.
- Les tests couvrent la séparation des catalogues.

Statut : implémenté et vérifié le 28 octobre 2026 (catalogues distincts
candidat / recruteur / admin renvoyés par l'API, interface dynamique,
déclencheurs réels pour nouvelle candidature, réponse à une invitation,
publication et expiration d'offre, routage des alertes admin via les
préférences personnelles, migration idempotente sans e-mail non demandé,
tests de séparation des catalogues).

### 20. Page recruteur des candidatures reçues

**Constat**
Les candidatures reçues sont visibles dans le dashboard recruteur, mais il
n'existe pas de page dédiée qui les regroupe par offre. Le recruteur ne peut
pas parcourir facilement l'ensemble des candidatures liées à une offre.

**Objectif**
Créer une page « Candidatures reçues » où chaque offre affiche ses
candidatures empilées.

**Actions**
- Ajouter une route et une entrée de navigation « Candidatures reçues ».
- Regrouper les candidatures par offre, avec le nombre total et le nombre de
  nouvelles.
- Afficher les candidatures en pile sous l'offre, avec possibilité de replier
  ou déplier.
- Afficher le nom, le score de correspondance, la date et le statut de chaque
  candidat.
- Ajouter des filtres par offre, statut et date, ainsi qu'une recherche.
- Relier chaque candidature à sa fiche détaillée et aux actions autorisées.
- Prévoir un état vide et une pagination.

**Critères d'acceptation**
- Le recruteur voit toutes les candidatures reçues, groupées par offre.
- Chaque offre affiche le total et le nombre de nouvelles candidatures.
- Les candidatures s'empilent sous l'offre et peuvent être ouvertes.
- Les actions de statut respectent les permissions du recruteur.
- La page reste utilisable avec un grand nombre de candidatures.

Statut : implémenté et vérifié le 28 octobre 2026 (route
`/recruteur/candidatures`, entrée de navigation « Candidatures reçues »,
endpoint groupé `/api/recruiter/applications/grouped`, total et nouvelles
par offre, piles repliables, score de correspondance, filtres offre /
statut / recherche / dates, pagination par offre, fiche candidat et
actions autorisées, état vide, plafond de 200 candidatures par offre avec
total exact).

## Priorité 2 : administration et identité visuelle

### 10. Notifications administrateur paramétrables

Statut : implémenté et vérifié le 27 octobre 2026 (équipe, catégories,
journal des alertes, test de routage sans envoi réel).

**Constat**
L'admin ne peut pas définir qui reçoit les alertes liées au panneau d'administration.

**Objectif**
Permettre de désigner des administrateurs et de choisir les catégories d'alertes.

**Actions**
- Ajouter une rubrique « Équipe d'administration » dans le panneau admin.
- Associer des adresses e-mail aux catégories d'événements.
- Permettre l'ajout, la modification et la suppression des destinataires.
- Journaliser chaque notification administrative.

**Critères d'acceptation**
- Au moins un destinataire doit etre défini pour les alertes critiques.
- Chaque catégorie peut etre activée ou désactivée indépendamment.
- Les destinataires sont testés sans envoi réel pendant les vérifications.

### 11. Branding des e-mails et affiches

**Constat**
Les e-mails et affiches actuels paraissent trop arrondis, trop « vibe codés », pas assez institutionnels.

**Objectif**
Obtenir un design sobre, professionnel et cohérent avec la charte OrientSkill AI.

**Actions**
- Créer une charte d'e-mail : couleurs, marges, typographie, signature.
- Réduire les rayons de bordure et supprimer les effets surchargés.
- Harmoniser les affiches d'offre et les visuels publics.
- Produire un jeu de gabarits réutilisables pour e-mails, affiches et notifications.

**Critères d'acceptation**
- Tous les e-mails partagent la meme structure visuelle.
- Aucun visuel n'utilise plus de deux couleurs d'accent.
- Le rendu reste lisible sur mobile, Gmail, Outlook et en impression.

Statut : implémenté et vérifié le 28 octobre 2026. Tous les e-mails
passent par un gabarit HTML commun (`email_branding.py`) avec version
texte de repli, signature de marque et pied de page à libellés courts.
SMTP envoie désormais un message `multipart/alternative` ; Brevo et
Resend reçoivent les deux versions. Les affiches et visuels publics
utilisent un fond clair imprimable, un bandeau institutionnel, des
rayons réduits et suppriment cercles et dégradés décoratifs. La charte
complète est documentée dans `docs/BRAND_GUIDE.md`.

### 12. Révision globale de l'identité visuelle

**Constat**
Plusieurs zones de l'interface paraissent encore trop arrondies ou génériques.

**Objectif**
Renforcer la lisibilité et la crédibilité visuelle de l'ensemble.

**Actions**
- Auditer les composants a forte bordure arrondie.
- Standardiser les rayons de bordure par type de composant.
- Améliorer les badges, cartes et entetes de section.
- Vérifier le contraste et l'accessibilité sur toutes les pages.

**Critères d'acceptation**
- Une seule échelle de rayons est utilisée sur toute l'application.
- Les badges et cartes deviennent plus institutionnels.
- Aucune régression d'accessibilité n'est introduite.

Statut : implémenté et vérifié le 28 octobre 2026. Une échelle unique
de six jetons remplace tous les rayons codés en dur : `xs` 4 px,
`sm` 6 px, `md` 8 px, `lg` 10 px, `xl` 12 px et `pill` 999 px. Les
badges, statuts et compétences sont rectangulaires ; les chips, filtres
et onglets utilisent le rayon `sm`. Les entêtes de section ont un filet
de séparation discret. Le vert institutionnel et l'orange brûlé ont été
assombris pour respecter le contraste AA. Un test d'audit
(`test_v33_visual_identity.py`) vérifie l'échelle, l'absence de rayons
hors jetons et onze combinaisons de contraste. Vérification visuelle
aux largeurs 1280, 768 et 375 px sur l'accueil, les opportunités, les
notifications, les candidatures recruteur et les recours admin.

### 21. Page de notifications pour l'admin

**Constat**
L'admin n'a pas de page de notifications dédiée. Les alertes administratives
sont dispersées ou envoyées par e-mail, sans boîte de réception commune.

**Objectif**
Fournir à l'admin une boîte de notifications centralisée, filtrable et reliée
aux actions à traiter.

**Actions**
- Ajouter une page « Notifications » dans l'espace admin.
- Lister les événements : demandes de vérification, recours, signalements,
  échecs d'ingestion et alertes critiques.
- Ajouter les filtres par catégorie, statut et date.
- Permettre de marquer comme lu, de traiter ou de renvoyer vers la page
  concernée.
- Afficher les compteurs non lus dans la navigation.
- Définir la durée de conservation et les droits d'accès.

**Critères d'acceptation**
- L'admin dispose d'une page de notifications dédiée.
- Chaque notification renvoie vers l'action correspondante.
- L'état lu ou non lu est conservé.
- Seuls les admins peuvent accéder à cette page.
- Les compteurs correspondent aux notifications affichées.

### 22. En-tête du dashboard recruteur à moderniser

**Constat**
L'en-tête du dashboard recruteur paraît daté et manque de hiérarchie visuelle.

**Objectif**
Obtenir un en-tête plus moderne, sobre et professionnel, cohérent avec la
charte OrientSkill.

**Actions**
- Reprendre la hiérarchie : accueil, entreprise, date et actions principales.
- Mettre en avant l'action « Publier une offre » et les indicateurs clés.
- Réduire les arrondis et les effets décoratifs.
- Améliorer la typographie, les espacements et le responsive.
- Vérifier le contraste et la lisibilité sur mobile.

**Critères d'acceptation**
- L'en-tête affiche clairement l'identité du recruteur et l'action principale.
- Les indicateurs clés sont lisibles sans surcharge.
- Le rendu est cohérent sur desktop et mobile.
- Aucune régression d'accessibilité n'est introduite.

## Priorité 0 : retours complémentaires du 27 octobre 2026

### 24. Le design fait partie du livrable

**Constat**
Le design est encore traité comme un habillage final, alors qu'il conditionne
la crédibilité et la compréhension du produit.

**Objectif**
Intégrer le design dès la conception de chaque fonctionnalité, sans le
revenir à plus tard.

**Actions**
- Ajouter une revue design à chaque ticket.
- Définir une charte de composants et l'appliquer dès le début.
- Interdire les mises en page « provisoires » non validées.
- Vérifier la cohérence visuelle à chaque livraison.

**Critères d'acceptation**
- Aucune fonctionnalité n'est livrée sans validation design.
- Les composants respectent la charte dès la première version.

### 25. Photo de profil pour l'entreprise ou le recruteur

**Constat**
Les entreprises et les recruteurs n'ont pas de photo de profil visible.

**Objectif**
Permettre à une entreprise ou à un recruteur de disposer d'une photo
représentative, comme les candidats.

**Actions**
- Ajouter un champ photo sur le compte entreprise et le compte recruteur.
- Permettre le dépôt depuis l'espace recruteur.
- Afficher la photo dans le profil, les offres et la messagerie.
- Prévoir un visuel neutre si aucune photo n'est fournie.

**Critères d'acceptation**
- Le recruteur peut ajouter et changer sa photo.
- La photo apparaît partout où l'identité est visible.
- Une entreprise sans photo conserve un rendu propre.

### 26. Parcours de suivi clair des actions

**Constat**
Le cycle de vie des candidatures et des entretiens n'est pas assez lisible.
Les deux parties ne savent pas toujours qui peut accepter, refuser ou inviter.

**Objectif**
Rendre chaque étape visible, compréhensible et liée aux droits réels de
chaque rôle.

**Actions**
- Définir une machine à états unique pour candidature et entretien.
- Afficher un fil chronologique clair côté candidat et côté recruteur.
- Préciser, pour chaque étape, qui peut agir et ce qui est conservé ou
  supprimé.
- Notifier les deux parties à chaque changement d'état.
- Empêcher toute action non autorisée par le rôle.

**Critères d'acceptation**
- Chaque action est visible, datée et attribuée au bon rôle.
- Le candidat et le recruteur voient le même état.
- Aucune action hors périmètre n'est possible.

### 27. Fichier iCalendar toujours à jour

**Constat**
Le fichier .ics téléchargeable reste valable pour la première proposition de
créneau. Les modifications suivantes ne sont pas correctement reflétées.

**Objectif**
Le fichier .ics doit refléter l'état courant de l'entretien, même après un
changement de créneau.

**Actions**
- Régénérer le fichier .ics à chaque modification.
- Incrémenter la séquence et le statut à chaque mise à jour.
- Invalider proprement les anciens liens sans casser les nouvelles invitations.
- Vérifier le comportement dans Google Calendar, Outlook et Apple Calendar.

**Critères d'acceptation**
- Chaque modification de créneau produit un fichier à jour.
- L'ancien fichier n'affiche plus un créneau obsolète.
- Le statut de l'événement suit la décision réelle.

### 28. Visuel d'offre par défaut selon le domaine

**Constat**
Certaines offres restent uniquement textuelles ou avec de simples initiales.

**Objectif**
Chaque offre doit avoir un visuel, fourni par l'entreprise ou issu d'une
banque d'images par domaine.

**Actions**
- Constituer une banque de visuels par domaine.
- Choisir automatiquement un visuel de repli selon le domaine.
- Permettre à l'entreprise de remplacer ce visuel par le sien.
- Afficher ce visuel sur la carte, la fiche et les partages.

**Critères d'acceptation**
- Aucune offre n'est publiée sans visuel.
- Le visuel de repli correspond au domaine de l'offre.
- L'entreprise peut toujours fournir son propre visuel.

### 29. Publication d'une offre depuis un visuel seul

**Constat**
Certains responsables RH arrivent uniquement avec l'affiche de l'offre et ne
veulent pas remplir un formulaire complet.

**Objectif**
Permettre de publier une offre à partir du visuel, avec un minimum de saisie.

**Actions**
- Ajouter un mode « publier depuis un visuel ».
- Extraire ou demander uniquement les champs indispensables.
- Générer un brouillon à partir du visuel.
- Laisser l'entreprise compléter les détails plus tard.
- Conserver la traçabilité et les règles anti-invention.

**Critères d'acceptation**
- Une offre peut être publiée avec un visuel et quelques champs.
- Aucune donnée n'est inventée.
- L'offre reste modifiable après publication.

### 30. Nouvelle iconographie du profil vérifié

**Constat**
L'icône actuelle ressemble à une icône de sécurité, pas à un badge de
vérification de profil.

**Objectif**
Obtenir un badge distinct, sobre et immédiatement compréhensible.

**Actions**
- Proposer de nouvelles variantes graphiques.
- Tester la lisibilité en 16 px.
- Vérifier la distinction avec les icônes de sécurité.
- Harmoniser le rendu sur fond clair et sombre.

**Critères d'acceptation**
- Le badge est distinct des icônes de sécurité.
- Il reste lisible en petite taille.
- Le design est validé par la direction produit.

### 31. Page agent : « toutes » par défaut

**Constat**
La page agent n'ouvre pas par défaut sur l'ensemble des opportunités.

**Objectif**
Afficher par défaut toutes les opportunités et laisser le candidat cliquer
sur « recommandé » pour voir la sélection de l'agent.

**Actions**
- Changer l'onglet par défaut de la page agent.
- Conserver l'accès direct aux recommandations.
- Garder les filtres et la recherche actifs.

**Critères d'acceptation**
- L'ouverture de la page montre toutes les opportunités.
- Le candidat peut basculer vers les recommandations en un clic.
- Aucune recommandation n'est perdue.

### 32. Paramètres approfondis du compte

**Constat**
Les paramètres du compte restent sommaires : sécurité, suppression et
données personnelles ne sont pas traités.

**Objectif**
Offrir un espace de gestion de compte complet et clair.

**Actions**
- Ajouter une section sécurité : mot de passe, MFA, sessions actives.
- Permettre la suppression du compte et des données.
- Permettre l'export des données personnelles.
- Clarifier la conservation et la suppression.
- Séparer les réglages par rôle.

**Critères d'acceptation**
- L'utilisateur peut sécuriser, exporter ou supprimer son compte.
- La suppression est explicite et réversible pendant un délai défini.
- Chaque réglage est appliqué immédiatement.

### 33. Iconographie des statuts « actif » et « disponible »

**Constat**
Les statuts « actif » et « disponible » manquent d'une représentation
graphique claire et classique.

**Objectif**
Obtenir une iconographie sobre et immédiatement lisible.

**Actions**
- Définir une famille d'icônes pour les statuts.
- Harmoniser la couleur, la forme et la taille.
- Vérifier la lisibilité et le contraste.
- Documenter l'usage de chaque statut.

**Critères d'acceptation**
- Chaque statut a une icône unique et reconnaissable.
- Le rendu reste sobre et institutionnel.
- Aucune ambiguïté ne subsiste entre deux statuts.

### 34. Sortir les ONG des programmes publics

**Constat**
Les opportunités liées aux ONG sont mélangées avec les programmes publics.

**Objectif**
Créer une page dédiée sous Opportunités, distincte des programmes publics.

**Actions**
- Créer une page « ONG et international » dans Opportunités.
- Y regrouper : opportunités dans les ONG, appels à projets et concours
  internationaux, bourses d'études internationales.
- Déplacer les contenus concernés.
- Mettre à jour la navigation et les filtres.

**Critères d'acceptation**
- Les ONG ne figurent plus dans Programmes publics.
- La page dédiée affiche les trois catégories.
- La navigation reste claire pour le candidat.

## Prochaines étapes

1. Valider cette roadmap avec la direction produit.
2. Chiffrer chaque lot de travail.
3. Commencer par les lots de priorité 0, notamment les points 13 à 16, 23
   et 24 à 34.
4. Traiter ensuite les points 17 à 20 de priorité 1.
5. Revoir l'ensemble dans une semaine après les premiers correctifs.
