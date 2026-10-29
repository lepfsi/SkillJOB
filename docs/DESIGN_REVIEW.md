# Revue design OrientSkill AI

Version du 29 octobre 2026. Ce document rend la revue design obligatoire
pour chaque fonctionnalité visible par l'utilisateur. Il complète
`docs/BRAND_GUIDE.md`, qui reste la référence pour les couleurs, la
typographie, les rayons, les e-mails et les visuels.

## 1. Principe

Le design n'est pas une finition. Il est évalué dès le cadrage, puis vérifié
avant de marquer une fonctionnalité comme livrée. Une fonctionnalité sans
revue design reste en revue, même si le code fonctionne.

La revue est consignée dans le ticket ou la pull request avec :

- la date de la revue ;
- le nom du relecteur ;
- les captures ou le lien de prévisualisation ;
- les écarts acceptés, s'il y en a, et leur justification.

## 2. Charte de composants de référence

Les composants existants sont la base obligatoire. Avant d'en créer un,
réutiliser ou étendre les composants et classes suivants.

| Composant | Référence | Règle |
| --- | --- | --- |
| Action principale | `.btn.btn-primary` | Une seule action principale par zone, libellé explicite. |
| Action secondaire | `.btn.btn-outline`, `.btn.btn-ghost` | Ne concurrence pas l'action principale. |
| Carte et panneau | `.panel`, `.dash-card` | Surface blanche, bordure fine, rayon de 8 à 12 px, aucun liséré. |
| Champ de formulaire | `.field` | Label visible, aide courte, erreur sous le champ. |
| Alerte | `.alert` | Ton calme, message court, action suivante claire. |
| Badge et statut | `.badge` | Forme rectangulaire, texte explicite, la couleur n'est jamais le seul indicateur. |
| État vide | `.empty` | Explique ce qui manque et propose l'action suivante. |
| Modale | `.modal-backdrop`, `.modal` | Une décision par modale, fermeture explicite, focus visible. |
| Avatar | `frontend/src/components/Avatar.jsx` | Photo ou initiales, jamais un cercle décoratif vide. |
| Score de correspondance | `frontend/src/components/MatchBadge.jsx`, `frontend/src/components/ScoreBar.jsx` | Symboles ✓ couverte, △ partielle, ○ manquante et explication, jamais un pourcentage seul. |

Les jetons de rayon (`--radius-*`), les couleurs et la typographie viennent
de `frontend/src/styles.css` et de `docs/BRAND_GUIDE.md`. Aucun composant ne
doit introduire une troisième couleur d'accent, un rayon hors échelle ou une
bordure d'accent unilatérale.

## 3. Checklist obligatoire

À valider avant de marquer une fonctionnalité livrée :

- [ ] Le besoin, l'action principale et le parcours utilisateur sont clairs.
- [ ] Les composants et jetons existants sont réutilisés avant toute création.
- [ ] Aucun liséré d'accent à gauche ni au-dessus d'une carte, d'un panneau
      ou d'un en-tête.
- [ ] Aucune mise en page provisoire non validée ne reste dans la livraison.
- [ ] Les états chargement, vide, erreur et succès sont traités.
- [ ] Le rendu est vérifié aux largeurs 1280 px, 768 px et 375 px, sans
      débordement horizontal.
- [ ] Le clavier, le focus et les contrastes WCAG AA sont vérifiés.
- [ ] Les libellés sont en français, sans emoji, et les actions sont
      explicites.
- [ ] Les captures ou le lien de prévisualisation sont joints au ticket.
- [ ] Le build frontend et les tests backend passent.
- [ ] Toute évolution de la charte met à jour `docs/BRAND_GUIDE.md` et les
      tests de branding concernés.

## 4. Mises en page provisoires

Une mise en page provisoire doit être identifiée comme telle dans le ticket
et ne peut pas être livrée. Si elle est visible par l'utilisateur, elle doit
respecter dès sa première version les couleurs, les rayons, la typographie
et les états de la charte. Une maquette non validée ne remplace pas une
revue design.

## 5. Critère de sortie

La fonctionnalité peut être marquée livrée lorsque la checklist est cochée,
que les preuves sont jointes et que le build frontend ainsi que la suite
backend passent. En cas de doute, la revue design est refaite avant la
livraison.
