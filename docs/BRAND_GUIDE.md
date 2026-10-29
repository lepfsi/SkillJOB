# Charte visuelle OrientSkill AI

Version du 28 octobre 2026. Ce document fixe les règles communes aux
e-mails, aux affiches d'offre, aux visuels publics et à l'interface.
L'objectif est une identité sobre, institutionnelle et lisible, sans
effets décoratifs inutiles.

## 1. Couleurs

Deux couleurs d'accent seulement. Toutes les autres teintes sont des
neutres ou des déclinaisons du vert primaire.

| Rôle | Valeur | Usage |
| --- | --- | --- |
| Vert institutionnel | `#0a6b4c` | En-têtes, boutons principaux, liens, badges forts |
| Vert profond | `#073d2b` | Bandeaux sombres, texte sur fond clair |
| Orange brûlé | `#b45309` | Filet d'accent, badges d'attention, deuxième accent |
| Fond clair | `#f4f7f5` | Arrière-plan des pages, des e-mails et des affiches |
| Surface | `#ffffff` | Cartes, tableaux, zones de contenu |
| Bordure | `#dbe3df` | Séparateurs et contours de cartes |
| Texte principal | `#16211c` | Titres et corps de texte |
| Texte secondaire | `#5b6a63` | Métadonnées, aides, pieds de page |

Règles :

- Ne jamais introduire une troisième couleur d'accent.
- Les teintes claires du vert (`#d7efe4`, `#bff3dd`, `#f2faf6`) sont des
  déclinaisons du vert primaire, pas des accents indépendants.
- Le texte blanc n'est utilisé que sur le vert institutionnel, le vert
  profond, l'orange brûlé ou le gris ardoise. Ces combinaisons doivent
  rester conformes au contraste WCAG AA.
- Les symboles de matching restent imposés : ✓ couverte, △ partielle,
  ○ manquante. La couleur ne doit jamais être le seul indicateur.

## 2. Typographie

- Interface : Poppins pour les titres, Inter pour le texte, avec repli
  système.
- E-mails : Arial, Helvetica, sans-serif. Aucune police distante, car
  les clients de messagerie la bloquent souvent.
- Affiches et visuels SVG : Arial, Helvetica, sans-serif pour garantir
  le rendu sans ressource externe.
- Les titres restent courts. Les textes longs sont découpés en
  paragraphes de deux à quatre lignes.

## 3. Échelle unique de rayons

Une seule échelle est utilisée dans toute l'application :

| Jeton | Valeur | Usage |
| --- | --- | --- |
| `--radius-xs` | 4 px | Badges, étiquettes, puces, petits boutons |
| `--radius-sm` | 6 px | Champs compacts, cartes secondaires |
| `--radius` | 8 px | Cartes standards, panneaux, boutons |
| `--radius-lg` | 10 px | Boutons principaux, zones interactives |
| `--radius-xl` | 12 px | Modales, grands panneaux, encarts |
| `--radius-pill` | 999 px | Filtres et pastilles de statut uniquement |

Les cercles restent réservés aux avatars et aux indicateurs ronds
(`border-radius: 50%`). Les cartes, badges et étiquettes ne doivent pas
utiliser de rayons supérieurs à 12 px. Les badges et compétences sont
rectangulaires, avec un rayon de 4 à 6 px.

## 4. Gabarit e-mail

Tous les e-mails passent par `backend/app/services/email_branding.py`.
Le message est envoyé en `multipart/alternative` : une version texte
brut de repli et une version HTML commune.

Structure HTML :

1. Bandeau vert profond avec le nom OrientSkill AI et la signature
   « Intelligence professionnelle ».
2. Filet orange de 3 px sous le bandeau.
3. Sur-titre « Notification » en vert.
4. Titre de l'e-mail, puis contenu en paragraphes.
5. Pied de page avec les liens de préférences et de désabonnement
   lorsqu'ils existent.
6. Signature de marque et URL publique.

Contraintes :

- Largeur maximale de 640 px, tableau centré, largeur fluide sur mobile.
- Styles en ligne uniquement, aucun fichier CSS externe.
- Aucune image externe : les logos sont du texte, donc rien n'est
  bloqué par Gmail ou Outlook.
- Les longues URL de pied de page sont affichées sous forme de libellés
  courts. L'URL complète reste dans le lien.
- Le texte brut contient toujours la signature et les liens bruts.
- Les e-mails critiques gardent la signature, mais n'ajoutent ni
  préférences ni désabonnement.
- Le rendu doit rester lisible sans images, sans CSS avancé et à
  l'impression. Le fond reste clair, le texte foncé.

## 5. Affiche d'offre

Gabarit `backend/app/services/poster.py`, format 1200 x 1500.

- Fond clair `#f4f7f5`, imprimable sans aplat sombre.
- Bandeau d'en-tête vert profond, mot-marque blanc, signature verte
  claire.
- Filet supérieur vert avec segment orange.
- Badge de candidature rectangulaire, rayon 4 px.
- Métadonnées en étiquettes blanches bordées, rayon 4 px.
- Carte de contenu blanche, bordure fine, rayon 8 px.
- Encart de conseil vert très clair, rayon 4 px.
- Aucun cercle décoratif, aucun dégradé de fond, aucune ombre.
- Les informations viennent uniquement de l'offre et de la
  configuration de la boîte interne. Aucune coordonnée n'est inventée.

## 6. Visuel public d'offre

Gabarit `backend/app/services/job_media.py`, format 1200 x 800.

- Dégradé limité à deux teintes de la même famille de domaine.
- Filet supérieur dans la couleur du domaine, avec un segment orange
  fixe de 180 px pour rappeler la marque.
- Étiquette de domaine rectangulaire, rayon 4 px.
- Initiales de l'entreprise dans un carré arrondi de 8 px, pas dans un
  cercle.
- Aucun halo radial, aucun cercle décoratif.
- Le visuel reste lisible en miniature LinkedIn et WhatsApp.

## 7. Interface

- Les cartes standards utilisent `--radius` (8 px), les grands panneaux
  `--radius-xl` (12 px) au maximum.
- Les entêtes de section ont un titre aligné, un espace régulier et un
  filet de séparation discret.
- Les badges, compétences et statuts sont rectangulaires. Les pastilles
  rondes sont réservées aux filtres et aux compteurs.
- Les ombres restent discrètes. La hiérarchie repose d'abord sur
  l'espacement, la typographie et un fond de surface.
- **Aucun liséré d'accent** (bordure colorée épaisse) à gauche ni au-dessus
  d'une carte, d'un panneau ou d'un en-tête. Une bordure fine tout autour
  reste possible pour délimiter un contenu, jamais un filet d'accent
  unilatéral.
- Les états de focus restent visibles au clavier.
- Aucun texte porteur d'information ne doit être en dessous du seuil de
  contraste AA.

## 8. Vérifications

- `backend/tests/test_v32_branding.py` vérifie le gabarit e-mail, la
  signature, les alternatives texte et HTML, l'affiche et le visuel
  public.
- Les tests d'envoi SMTP, Brevo et Resend vérifient la présence du HTML
  et du texte brut.
- Les captures de contrôle sont conservées dans `.smoke/visual/` et ne
  sont jamais versionnées.
- Toute évolution de la charte doit mettre à jour ce document et les
  tests concernés.
