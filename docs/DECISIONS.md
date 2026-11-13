# Décisions techniques

Choix actés pour MonPetitProducteurLocal. Ce document garde la trace des décisions et de leur raison d'être — le modifier quand une décision évolue.

## Licence : Double licence (GNU AGPL-3.0 & Commerciale / SaaS)

Anti-fourke fermée et bien commun : toute instance publique auto-hébergée modifiée doit partager ses modifications sous AGPL-3.0. Une voie commerciale / SaaS éthique est proposée par Cartotrac pour les déploiements managés. `LICENSE` = texte anglais AGPL-3.0 de référence ; `LICENSE.fr.md` = détails du modèle de double licence ; `CONTRIBUTING.md` = accord de cession/contribution (CLA).

## Stack : Django 5, templates classiques

Python 3.11+ / Django 5, templates HTML/CSS sobres, **pas de framework front**. Back-office : l'admin Django. Objectif : maintenable par des contributeurs backend, léger à héberger.

## Base de données : PostgreSQL en prod, SQLite en mono-ferme

- **PostgreSQL** (natif AlwaysData) pour les instances mutualisées : champs **JSONB** pour les attributs personnalisés des produits et les paramètres (réseaux, messagerie).
- **SQLite** acceptable pour une instance mono-ferme (Raspberry Pi, très petit hébergement) : base = un fichier, sauvegardable/copiable d'un coup.
- **MySQL n'est pas supporté** — choix volontaire.
- Les migrations sont générées sur le serveur (`makemigrations portal`), jamais versionnées dans le dépôt.

## Images : liens externes, zéro hébergement

Logos et photos de profil/produits peuvent être des **fichiers** (champs ImageField) mais surtout des **URLs externes** (drive, cloud, réseau) : rien n'est hébergé par le portail, aucune dépendance à un stockage objet. Un widget d'aperçu dynamique valide visuellement le lien.

## Quantités hebdo : estimation publiée + dispo restante

Les quantités saisies par le producteur restent **des estimations**, mais la page de commande affiche désormais la **dispo restante = estimation − quantités déjà commandées sur la semaine** (commandes en attente ou validées), et refuse un prélèvement supérieur. **Sans récolte publiée**, la commande reste possible sur le **cataloge au prix de référence**, avec avertissement explicite : quantités soumises à validation et disponibilités réelles du cultivateur. **Seules les quantités effectivement livrées dans les paniers restent la source du décompte de production** (export comptable).

## Commandes : portail + saisie producteur, identité vivante

Les commandes arrivent via le portail (avec ou **sans compte client** : nom + téléphone obligatoires au format français, e-mail optionnel réservé newsletter) ou sont **saisies directement par le producteur** (rattachées au compte client si l'e-mail correspond). Les commandes et paniers sont **regroupés visuellement par jour de livraison** (sections dépliables, dernier jour ouvert). L'identité affichée est **vivante** : modifier son profil met à jour rétroactivement commandes et paniers (commande de maintenance `resynchroniser_clients`).

## Rôles : propriétaire + équipe multi-comptes

Le compte porteur de l'exploitation est **propriétaire** (fiche, équipe, paramètres, catalogue standard) ; des comptes **membres** rattachés au même SIRET gèrent le courant (récoltes, commandes, paniers, points, clients, édition rapide des produits). Chaque membre garde son identité propre (photo, e-mail) affichée côté maraîcher et sur la vitrine (équipe de la ferme).

## Paniers : n°1..X par jour et par point de livraison

Un **point de livraison est obligatoire à la validation** d'une commande : les paniers sont numérotés 1..X par **(exploitation, jour, point)**. Les points de livraison sont **géolocalisés** (clic carte ou géocodage Nominatim de l'adresse) et la position est **transmise au client** (adresse + lien carte) dès que son panier passe en prêt/livré.

## Communication : SMTP et SMS du producteur

Newsletters et annonces sont créées et diffusées depuis l'onglet **Publications** vers les e-mails connus (comptes clients + commandes sans compte). L'envoi utilise le **SMTP propre à l'exploitation**, configurable par le propriétaire dans la page **Paramètres** (sinon le backend du serveur : console, ou AlwaysData `EMAIL_HOST=localhost`), et une **passerelle SMS paramétrable** est prévue pour la disponibilité hebdo des produits. Le portail ne s'interpose pas entre le producteur et ses clients.

## Catalogue standard embarqué

Un **catalogue de ~80–120 produits types** est embarqué avec des **illustrations emojis/SVG** incluses au dépôt : choix explicite — **zéro dépendance externe, zéro contrainte de licence** (pas Wikimedia). Filtres catégorie/saison/nom ; le producteur copie en cochant les produits qu'il veut dans son catalogue personnel, et peut créer ses propres produits **directement en mode édition du dashboard** (ajout produit/catégorie, reclassement ▲▼, changement de catégorie), sans page dédiée.

## Cartographie : Leaflet + données ouvertes

Carte Leaflet. **Fond de plan : Plan IGN V2 (Géoplateforme, WMTS sans clé)** — les tuiles OSM directes renvoient 403 pour un usage web et CARTO exige une clé ; l'IGN a ouvert ses données, c'est la source la plus fiable. **Ortho : Esri World Imagery** (sans clé). Superpositions administratives **Régions/Départements** (france-geojson) avec **seuils de zoom** (grisées en dessous, chargement refusé) et **étiquettes départements** (n° + nom) au-delà du zoom 8 ; la couche Communes a été retirée (trop lourde, le fond IGN suffit). Géolocalisation navigateur ; **sélecteur de position par clic** (ferme, points de livraison) et **géocodage Nominatim** des adresses.
