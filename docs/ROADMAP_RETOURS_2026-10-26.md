# Roadmap de traitement des retours produits

Date de revue : lundi 26 octobre 2026
Source : retours utilisateurs et tests terrain du 25 octobre 2026.
Statut : document de travail. Aucune de ces remarques n'est encore considérée comme validée avant la revue.

## Objectif

Corriger les irritants de confiance, de compréhension et de pilotage avant d'élargir la plateforme. Les points ci-dessous sont classés par priorité produit, avec pour chacun :

- le constat observé,
- l'objectif cible,
- les actions de mise en oeuvre,
- les critères d'acceptation.

## Priorité 0 : confiance et cohérence du parcours

### 1. Validation de la vérification de profil sans notification

**Constat**
La vérification d'un profil peut être validée par l'administration sans que le candidat soit notifié.

**Objectif**
Le candidat doit savoir, sans rafraichir la page, que son profil est devenu vérifié.

**Actions**
- Ajouter un événement de notification `profile_verified`.
- Brancher la validation côté admin sur ce même événement.
- Afficher la notification dans la rubrique Notifications et dans le badge du menu.
- Envoyer un e-mail uniquement si l'utilisateur a activé ce type d'alerte.

**Critères d'acceptation**
- Toute validation génère une notification visible côté candidat.
- Le badge « profil vérifié » apparaît sans rechargement manuel.
- Le journal `notification_log` conserve une trace de l'envoi éventuel.

### 2. Notifications visibles avant la création du compte

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

## Priorité 1 : parcours candidat et recruteur

### 4. Iconographie du profil vérifié

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

### 5. Paramètres de conversation mal placés

**Constat**
Les réglages d'historique sont accessibles depuis une zone de défilement, loin de la conversation visible.

**Objectif**
Le contrôle de l'historique doit être dans la conversation elle-meme.

**Actions**
- Déplacer les boutons « éphémère » et « effacer » dans l'entete du fil de discussion.
- Ajouter un bouton « Fermer la conversation ».
- Ouvrir la conversation uniquement sur action explicite du candidat.
- Afficher une liste des conversations précédentes avec date et dernier message.

**Critères d'acceptation**
- Aucun réglage d'historique n'est accessible hors du fil de conversation.
- Une conversation fermée n'est pas rouverte automatiquement au rechargement.
- L'utilisateur peut reprendre une conversation précédente depuis une liste claire.

### 6. Assistant de publication d'offre inopérant

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

## Priorité 2 : administration et identité visuelle

### 10. Notifications administrateur paramétrables

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

## Prochaines étapes

1. Valider cette roadmap avec la direction produit.
2. Chiffrer chaque lot de travail.
3. Commencer par les lots de priorité 0.
4. Revoir l'ensemble dans une semaine après les premiers correctifs.
