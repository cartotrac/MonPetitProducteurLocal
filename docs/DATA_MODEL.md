# Structure de données définitive

> Document de référence pour les modèles Django (`portal/models.py`).
> Convention : **noms de tables et de champs en français**, sans accent dans
> les identifiants (`numero`, `quantite`…). Les modèles déjà en place en
> V1 sont signalés **[V1]**, les ajouts prévus **[V2]** (issues #1–#9).

## Principes

- **PostgreSQL** en prod : attributs libres en **JSONB** (SQLite accepté en
  mono-espace : Django dégrade `JSONField` en texte — OK, aucun filtrage
  avancé requis sur ces attributs).
- Les quantités hebdo sont des **estimations** : aucun décompte à la commande.
  Seules les quantités **livrées dans les paniers** sont décomptées.
- **Seules les commandes validées par l'exploitant puis livrées** persistent
  en base ; les paniers non confirmés ou abandonnés sont **purgés**.
- **Clients loggués** : historique complet rattaché au compte.
  **Clients sans compte** : seuls les éléments de session (panier navigateur)
  et **l'enregistrement de la commande à l'instant t** sont conservés —
  l'identité est le **contact (e-mail OU téléphone) + nom**.
- Chaque producteur possède **ses propres catégories et produits** ; le
  catalogue standard embarqué n'est qu'un **point de départ copiable**.
- Les prix et quantités sont **figés** (copie) au moment de la commande :
  modifier un produit n'altère jamais l'historique.
- **Fichiers** : seuls les visuels de l'exploitant sont importés, sous
  `media/exploitants/{id}/` avec un **naming explicite** et un **quota par
  type**. Le catalogue standard vit en emojis/SVG embarqués : zéro fichier.

## Espaces pro

### Exploitant **[V1]**

Un **espace pro local** : exploitation agricole, fromagerie, conserverie,
foodtruck, traiteur ou restaurant — le vocabulaire du portail s'adapte au
métier (« Ma ferme », « Mon foodtruck », « Mon restaurant »…) via les
libellés `titre_fiche` / `libelle_fiche` / `vocab`.

| Champ | Type | Notes |
|---|---|---|
| user | OneToOne User | compte propriétaire |
| nom_espace | Char(150) | nom de l'espace (ancien `nom_ferme`, renommé par RENAME COLUMN) |
| slug | Slug(160) unique | adresse publique, auto |
| siret | Char(14) | clé de Luhn validée en forme |
| activite | Choices | maraîcher, arboriculteur, éleveur, fromager, apiculteur, micro-brasseur, conserverie, foodtruck, traiteur, restaurant, autre |
| specialite | Char(12), **OPTIONNELLE** | listes propres à chaque métier : foodtrucks (pizza, burger, tacos…), traiteurs (buffets, pièces cocktail…), restaurants (bistronomie, cuisine du marché…), éleveurs (bovine, volailles…) ; **vide pour les autres activités** — jamais exigée à l'inscription |
| mode_production / mode_fonctionnement | Choices | AB/perma/paysanne… ; récoltes hebdo vs boutique à date |
| latitude / longitude | Float, null | position sur la carte |
| visible / est_demo | Boolean | vitrine publique ; espace de démonstration |

### MembreExploitation **[V1]**

Équipe **multi-comptes** : `user` + `exploitant` (uniques ensemble) —
une même personne peut être rattachée à plusieurs espaces ; le
propriétaire (OneToOne `Exploitant.user`) administre la fiche, l'équipe
et les paramètres, les membres gèrent le courant.

## Catalogue

### Categorie **[V2 — issue #5]**

Catégories **définies par chaque exploitant**.

| Champ | Type | Notes |
|---|---|---|
| exploitant | FK Exploitant, CASCADE | `related_name="categories"` |
| nom | Char(80) | ex : « Légumes d'hiver » |
| slug | Slug(100) | auto, unique par exploitant |
| position | PositiveSmallInt | tri d'affichage |

`unique_together = ("exploitant", "nom")`

### Produit **[V1 → évolué en V2]**

| Champ | Type | Notes |
|---|---|---|
| exploitant | FK Exploitant, CASCADE | |
| categorie | FK Categorie, SET_NULL, null | remplace le champ texte `category` |
| nom | Char(150) | |
| description | Text, blank | |
| unite_vente | Char(2) choices | kg / pièce / botte / barquette |
| illustration | Image, blank | photo perso ; sinon emoji/SVG du standard |
| attributs | JSONField, default dict | `{"variété": "Butternut", "label": "AB", "saison": ["été", "automne"]}` — JSONB |
| origine_standard | FK ProduitStandard, SET_NULL, null | traçabilité de la copie |
| perso | Boolean | produit créé pour l'usage propre de l'exploitant |
| prix | Decimal(6,2) | tarif de référence, modifiable librement |
| actif | Boolean | visible ou non dans la vitrine |

### ProduitStandard **[V2 — issue #1]**

Catalogue standard embarqué (~80–120 produits types), en données de départ,
**lecture seule** pour les exploitants.

| Champ | Type | Notes |
|---|---|---|
| nom | Char(150) unique | « Carotte » |
| categorie | Char(80) | « Légumes racines » (catégorie standard simple) |
| unite_vente | Char(2) choices | kg / pièce / botte / barquette |
| saisons | JSONField | `["printemps", "été"]` → filtre saison |
| emoji | Char(8) | illustration embarquée 🥕 (zéro dépendance) |
| svg | Text, blank | SVG inline optionnel |

Filtres : catégorie, saison, recherche nom. Copie cochable →
`Produit.objects.create(origine_standard=…)` par exploitant.

## Récoltes et paniers

### SemaineRecolte / LigneRecolte **[V1]**

Estimations hebdo, prix par ligne, aucune réservation de stock. L'exploitant
paramètre chaque semaine **ce qui est visible** côté vitrine.

### Commande **[V1 → évoluée en V2 — issues #2, #6]**

Une commande, **du portail ou saisie par l'exploitant**, porte **toujours
l'identité contact du client**, loggué ou non.

| Champ | Type | Notes |
|---|---|---|
| exploitant | FK Exploitant, CASCADE | `related_name="commandes"` |
| client | FK Utilisateur, SET_NULL, null | null si client sans compte |
| nom_client | Char(150) | **toujours rempli**, figé à l'instant t |
| email_client | EmailField, blank | **e-mail OU téléphone obligatoire** |
| telephone_client | Char(20), blank | (contrainte de formulaire, pas en base) |
| statut | Choices | `NOUVELLE` / `VALIDEE` / `REFUSEE` ; livrée → statut porté par le `Panier` |
| saisie_exploitant | Boolean | saisie directe (issue #2) |
| panier_souhaite | OneToOne Panier, null | généré à la validation |
| creee_le | DateTime, indexé | |

**Clé de regroupement client** (vue « commandes par client » de l'exploitant) :
`exploitant + (client si loggué, sinon email_client ou telephone_client)`.
Un même contact retrouve ses commandes groupées, loggué ou non. À terme,
lorsqu'un contact crée un compte, ses commandes passées (même e-mail/tél)
peuvent lui être **rattachées**.

### LigneCommande **[V1]**

Historique du panier **souhaité** — figé, jamais modifié.

| Champ | Type | Notes |
|---|---|---|
| commande | FK Commande, CASCADE | `related_name="lignes"` |
| produit | FK Produit, PROTECT | |
| quantite | Decimal(8,2) | quantité demandée |
| prix_unitaire | Decimal(6,2) | **tarif figé au moment de la commande** |

### Panier **[V2 — issues #2, #6, #8]**

Panier **numéroté**, préparé pour un client, un jour de livraison.

| Champ | Type | Notes |
|---|---|---|
| exploitant | FK Exploitant, CASCADE | |
| client | FK Utilisateur, SET_NULL, null | null si client sans compte |
| nom_client | Char(150) | figé : identité conservée même sans compte |
| email_client / telephone_client | Email/Char(20) | figés, copiés de la commande |
| numero | PositiveSmallInt | **n°1..X par client et par jour** — (dernier n° du couple client/jour) + 1 ; la clé de numérotation = la même clé de regroupement que la commande |
| date_livraison | Date, indexé | jour de livraison réel |
| creneau | FK CreneauLivraison, SET_NULL, null | |
| point_livraison | FK PointLivraison, SET_NULL, null | |
| commande | FK Commande, SET_NULL, null | origine portail ; null si saisie directe |
| statut | Choices | `PREPARATION` / `PRET` / `LIVRE` / `RECU` |
| total | Decimal(8,2) | |

`unique_together = ("exploitant", "client", "date_livraison", "numero")`

### LignePanier **[V2]**

Contenu **effectivement livré** — LA source du décompte de production.

| Champ | Type | Notes |
|---|---|---|
| panier | FK Panier, CASCADE | `related_name="lignes"` |
| produit | FK Produit, PROTECT | |
| quantite | Decimal(8,2) | quantité validée par l'exploitant |
| prix_unitaire | Decimal(6,2) | **tarif figé au moment de la commande** |

**Export comptable CSV** (issue #8) : produit, quantité, prix, total, date de
livraison, client (nom + contact) — uniquement `statut = LIVRE / RECU`.

### Interface exploitant : suivi visuel des commandes par client **[V2 — issues #2, #6]**

L'écran « Mes clients » de l'exploitant liste les clients **loggués ou non**,
regroupés par la clé de regroupement ci-dessus, avec pour chacun :
- nom, contact (e-mail OU tél), badge « compte / sans compte » ;
- nombre de paniers livrés, dernière commande, paniers en préparation ;
- l'historique complet des paniers **livrés** (les commandes non validées
  n'apparaissent pas : elles sont purgées) ;
- pour les clients sans compte : uniquement **l'enregistrement de la
  commande à l'instant t** (figé) — pas d'historique de navigation ni de
  session, ceux-ci restent dans le navigateur.

## Livraison

### PointLivraison / CreneauLivraison **[V1]**

Inchangés. Écrans exploitant dédiés prévus (issue #9).

## Communication **[V2 — issue #3]**

### ModeleMessage

Modèles personnalisables, placeholders `{{ client }}`, `{{ panier }}`,
`{{ espace }}`, `{{ creneau }}`…

| Champ | Type | Notes |
|---|---|---|
| exploitant | FK Exploitant, CASCADE | `unique_together ("exploitant", "type")` |
| type | Choices | `CONFIRMATION_COMMANDE` / `PANIER_PRET` / `LIVRAISON_FAITE` / `BULLETIN` / `ANNONCE` |
| canal | Choices | `EMAIL` / `SMS` |
| objet | Char(200) | |
| corps | Text | placeholders inclus |
| actif | Boolean | un actif par (exploitant, type, canal) |

Contenu **par défaut fourni en fixture** et éditable ; **fallback sur le
défaut** si le modèle personnalisé est cassé. L'envoi utilise le contact
figé dans la commande (e-mail OU téléphone selon le canal et les
préférences) — fonctionne donc aussi pour les clients sans compte.

### Bulletin / Annonce

| Modèle | Champs | Notes |
|---|---|---|
| Bulletin | exploitant, semaine (FK SemaineRecolte nullable), objet, corps, envoye_le | envoyé aux clients abonnés |
| Annonce | exploitant, objet, corps, envoye_le | annonce ponctuelle (« paniers disponibles ») |

### PreferenceContact

Par couple client ↔ exploitant (clients loggués uniquement).

| Champ | Type | Notes |
|---|---|---|
| client | FK Utilisateur, CASCADE | `unique_together ("client", "exploitant")` |
| exploitant | FK Exploitant, CASCADE | |
| veut_bulletin | Boolean, default True | |
| veut_annonces | Boolean, default True | |
| canal | Choices | `EMAIL` / `SMS` | `SMS` → n° du ProfilClient requis |

### ConfigMessagerie

SMTP et passerelle SMS **de l'exploitant** (jamais centralisés).

| Champ | Type | Notes |
|---|---|---|
| exploitant | OneToOne Exploitant | |
| smtp_hote / smtp_port / smtp_utilisateur / smtp_mot_de_passe / smtp_expediteur | Char/Int | mot de passe chiffré au repos, jamais exporté |
| passerelle_sms | Choices | `FREE` / `OVH` / `TWILIO` / `HTTP_PERSONNALISE`… |
| config_sms | JSONField | endpoint + identifiants (chiffrés) |
| quota_journalier / heures_calmes | SmallInt / Char | garde-fous anti-spam |

## Vitrine **[V2 — issue #4]**

### ParametresVitrine

| Champ | Type | Notes |
|---|---|---|
| exploitant | OneToOne Exploitant | |
| titre_accroche / texte_accroche | Char/Text | bloc d'accueil personnalisé |
| couleur_theme | Char(7) | accent (#RRGGBB) |
| image_banniere | Image | sous `media/exploitants/{id}/banniere.jpg` |
| afficher_recolte / afficher_catalogue / afficher_creneaux | Boolean | sections visibles |
| reseaux | JSONField | `{"facebook": "…"}` |

## Système de fichiers (naming explicite, volumes maîtrisés)

Chaque exploitant a un dossier dédié `media/exploitants/{id}/` :

| Fichier | Règle | Quota |
|---|---|---|
| `logo.png` | 1 seul, écrasé à la mise à jour | 1 |
| `banniere.jpg` | 1 seul, écrasée | 1 |
| `espace-*.jpg` | photos de l'espace, slug explicite | ≤ 10 |
| `produits/{slug_produit}.jpg` | 1 image par produit, écrasée à la mise à jour | 1 par produit |

- Écrasement plutôt qu'accumulation : **pas de versions orphelines**.
- Compression/redimensionnement automatique à l'import (taille max par image).
- Zéro fichier pour le catalogue standard (emojis/SVG embarqués).

## RGPD (rappel, voir canvas dédié)

- Visiteur sans compte : rien de stocké au-delà de la session anonyme ;
  la commande sans compte conserve **uniquement l'instant t** (identité
  contact + lignes figées).
- La clé de regroupement client est visible de l'exploitant pour ses
  commandes uniquement — jamais l'historique global du client.
- Suppression du compte : `client` = null, `nom_client` et contacts figés
  conservés sur l'historique livré (preuve comptable) ; les commandes sans
  compte peuvent être anonymisées sur demande (droit à l'effacement).

## Historique des modifications

| Version | Changement |
|---|---|
| 0.4 | Notion « ferme » → « espace pro » : champ `nom_ferme` renommé `nom_espace` (RENAME COLUMN réel, sans perte), libellés adaptés au métier, spécialité OPTIONNELLE par liste de métier, placeholder `{{ espace }}` |
| 0.3 | Commande porte l'identité contact (e-mail OU tél + nom) ; regroupement clients loggués/non ; écran suivi par client |
| 0.2 | Noms de tables et champs en français ; purge des commandes non livrées ; système de fichiers/naming/quota |
| 0.1 | Première rédaction |
