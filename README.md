# 🌱 MonPetitProducteurLocal

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)

**Portail web libre de mise en relation et de gestion pour les producteurs et pros locaux — maraîchers, arboriculteurs, éleveurs, fromagers, apiculteurs, foodtrucks, traiteurs, restaurants… — et leurs clients : vitrine, commandes, paniers hebdomadaires et communication directe (e-mail/SMS).**

Le producteur crée sa vitrine en ligne, publie ses récoltes et son planning de livraison, reçoit et gère ses commandes et ses clients (validation, paniers numérotés préparés pour chaque jour de livraison), et communique directement avec eux : newsletter de la semaine, annonce de la mise à disposition des paniers, validation des livraisons. Le client découvre les producteurs près de chez lui, commande ses paniers et suit ses livraisons.

> ⚠️ **État du projet** : V1 en cours de construction — la structure est posée, les fonctionnalités s'enrichissent itérativement. Contributions et retours terrain bienvenues !

## Pour qui ?

- 🧑‍🌾 **Les petits producteurs et pros locaux** (maraîchers, arboriculteurs, éleveurs, fromagers, apiculteurs, foodtrucks, traiteurs, restaurants…) : vitrine publique gratuite, catalogue illustré par activité, récoltes hebdo, planning de livraison, gestion des commandes et de la communication client
- 🛒 **Les clients** : recherche par producteur, produit ou localisation, consultation libre sans compte, commande en quelques clics, favoris et recommande de commandes passées
- 🌍 **Les collectivités, AMAP et associations** : déployer une instance pour leur territoire — le code est libre et réplicable

## La page d'accueil

- un **bandeau** de navigation (logo, accès comptes) ;
- un bouton **« Chercher mon producteur ou un produit »** et un bouton **« Je suis producteur — rejoindre le réseau »** ;
- une **hero section** : présentation du portail, sa philosophie (circuits courts, indépendance des maraîchers, bien commun) et ses fonctionnalités clés ;
- une **carte de France** (Leaflet / fond IGN) des producteurs **catégorisés par mode de production** — AB, permaculture, agriculture paysanne, raisonnée, conventionnelle — avec légende filtrante et **géolocalisation de l'utilisateur** pour recentrer la carte sur sa position.

## Fonctionnalités (cible V1/V2)

| Espace | Fonctions |
|---|---|
| **Public** | Landing avec carte des producteurs, recherche multi-critères (producteur, produit, ville, département, **activité**), pages publiques des espaces pro (logo, présentation, certification, badge activité, produits avec emoji, récolte de la semaine, équipe, points de livraison géolocalisés, créneaux, réseaux sociaux) ; **mentions légales** (éditeur, hébergement, RGPD, philosophie, gouvernance) et plan du site complet en pied de page — **logo et site de l'admin de l'instance** (réglable via `INSTANCE_ADMIN`) |
| **Producteur** | Inscription simplifiée (nom de l'espace pro, **activité**, ville, code postal, localisation par clic carte) ; **spécialité OPTIONNELLE**, listes dédiées par métier (foodtruck, traiteur, restaurant, éleveur) ; **catalogues de produits types par activité** (maraîcher, arboriculture, élevage, fromagerie, ruche…) importables en un clic, onglets par activité ; catalogue illustré édité **directement en mode édition du dashboard** (ajout, renommé, reclassement ▲▼, changement de catégorie, catégories renommables/supprimables sans perdre les produits, retrait de produits en conservant l'historique) ; **équipe multi-comptes** : le propriétaire administre (fiche, équipe, paramètres, catalogue standard), des membres rattachés au SIRET gèrent le courant |
| **Dashboard** | Une colonne avec **ancres de navigation** (commandes, produits, récoltes, points, vitrine) ; hero météo en direct ; bandeau des créneaux ; **badges de statut** (à traiter orange, en cours jaune, validée verte) ; rubrique produits **repliée par défaut** ; **aperçu de la vitrine en direct** en bas de page |
| **Récoltes & dispo** | Saisie des **dispos hebdo = estimations** groupées par catégorie, **reprise automatique des valeurs de la semaine précédente** et rechargement depuis n'importe quelle semaine ; la page de commande affiche la **dispo restante de la semaine** (estimation − quantités déjà commandées) ; **sans récolte publiée, commande possible sur le catalogue** avec avertissement « quantités soumises à validation » |
| **Commandes** | Via le portail (saisie directe depuis la vitrine, quantités pré-remplies, **recommande d'une commande annulée en un clic**) **ou saisies par le producteur** ; validation / **refus motivé** (phrases proposées ou motif libre, visible par le client) ; filtres colorés par statut (à traiter orange, validées, refusées rouge, annulées client gris) ; **paniers numérotés n°1..X par jour et par point de livraison** ; commandes/paniers **regroupés par jour** (sections dépliables) côté producteur et client ; position du point **transmise au client** (adresse + lien carte) au passage en prêt/livré ; **export comptable des paniers livrés** (CSV) |
| **Paniers** | Ajustement ligne à ligne (souhaité client vs livré, quantités propres par unité : kg décimal, pièces/bottes/barquettes entières) ; **paniers « Livré » / « Reçu » verrouillés en lecture seule** (le contenu livré sert au décompte de production et à l'export comptable) ; **filtres par statut (colorés) et par point de livraison** ; **export CSV** |
| **Client** | Commande **avec ou sans compte** (nom + téléphone obligatoires, e-mail optionnel pour la newsletter), mention « commandé à Nom de l'exploitation », suivi et annulation, badge « en cours de traitement » ; **« Mes commandes » : cartes dépliables (repliées par défaut), filtres colorés** (à traiter orange, validées, refusées/annulées regroupées en rouge, paniers prêts, paniers retirés en gris), **quantités estimées** affichées sur les commandes modifiables, **vue calendaire hebdo alternative**, **validation de la réception** quand le panier est prêt (statut final « Reçu / retiré ») ; **identité vivante** : le profil mis à jour remonte rétroactivement dans commandes et paniers ; **favoris** (« Mes producteurs », vignettes unifiées avec la recherche, médaillon doré ✓ SIRET vérifié) et reprise de commande |
| **Communication** | Onglet **Publications** : newsletter de la semaine et annonces, diffusion e-mail ; **annonce SMS de la mise à disposition des paniers** ; envoi via **le SMTP propre à l'exploitation** (page Paramètres) et **la passerelle SMS de son choix** |
| **Paramètres** | Page unique **Profil / Espace / Équipe / Messagerie** — la rubrique Espace s'intitule selon le métier (« Ma ferme », « Mon foodtruck », « Mon restaurant »…) — SMTP + passerelle SMS par espace, propriétaire uniquement |
| **Admin** | Back-office Django complet (`/admin/`) |

## Feuille de route

Le backlog détaillé est suivi dans les [issues du dépôt](https://github.com/cartotrac/MonPetitProducteurLocal/issues) :

- [x] [#1 — Catalogue de produits standard embarqué (emojis/SVG libres) avec filtres](https://github.com/cartotrac/MonPetitProducteurLocal/issues/1)
- [x] [#2 — Saisie directe de commandes par le producteur](https://github.com/cartotrac/MonPetitProducteurLocal/issues/2)
- [x] [#3 — Communication producteur ↔ clients : newsletter, annonces, confirmations e-mail/SMS](https://github.com/cartotrac/MonPetitProducteurLocal/issues/3) *(SMS : passerelle paramétrable, envoi à brancher)*
- [x] [#4 — Vitrine producteur personnalisable](https://github.com/cartotrac/MonPetitProducteurLocal/issues/4)
- [x] [#5 — Catégories personnalisables et attributs libres des produits (JSONB)](https://github.com/cartotrac/MonPetitProducteurLocal/issues/5)
- [x] [#6 — Paniers numérotés par jour de livraison et par point](https://github.com/cartotrac/MonPetitProducteurLocal/issues/6)
- [x] [#7 — Géocodage des adresses + carte (clic, Nominatim, fond IGN)](https://github.com/cartotrac/MonPetitProducteurLocal/issues/7) *(clustering à venir)*
- [x] [#8 — Export comptable des paniers livrés (CSV)](https://github.com/cartotrac/MonPetitProducteurLocal/issues/8)
- [x] [#9 — Écrans producteur : points de livraison et créneaux hebdo](https://github.com/cartotrac/MonPetitProducteurLocal/issues/9)

Plus loin : panier multi-producteurs, mutualisation par département / pays, automatisation du déploiement.

## 🌱 Philosophie

MonPetitProducteurLocal est un **bien commun numérique** : un outil libre, décentralisé et réplicable, pensé pour renforcer les circuits courts et l'indépendance des petits producteurs — pas pour les capter via un intermédiaire. La carte, le catalogue, la commande et la communication client appartiennent à chaque espace pro ; le portail se contente de les mettre en relation avec leur clientèle de proximité. Chaque collectivité, AMAP ou association peut déployer sa propre instance sur son territoire, sous son contrôle.

## 🏛️ Gouvernance

- **Code ouvert** sous AGPL-3.0 : toute instance publique modifiée doit partager ses modifications.
- **Décisions et conception documentées publiquement** ([docs/DECISIONS.md](docs/DECISIONS.md)) ; les retours terrain des producteurs orientent la feuille de route.
- **Admin d'instance local** : l'instance est animée par son admin (identité et site affichés en pied de page, réglables via `INSTANCE_ADMIN` dans les settings), responsable de l'animation du territoire — mais les données de production et de clientèle **appartiennent aux producteurs**, qui gardent leurs propres SMTP / passerelle SMS.
- **Pas de données revendues, pas de publicité, pas de profilage.**

## 🔒 Conformité RGPD

- **Minimisation** : seules les données strictement nécessaires à la mise en relation producteur / client sont enregistrées (identité, coordonnées de contact, historique des commandes pour les comptes ; identité saisie pour les commandes sans compte).
- **Finalité déterminée** : traitement des commandes et communication producteur ↔ client (confirmations, annonces de paniers prêts) — rien d'autre.
- **Hébergement UE** (AlwaysData, Union européenne) ; les visuels des vitrines sont hébergés par les producteurs eux-mêmes (liens externes).
- **Durées de conservation limitées** : purge des commandes non validées/livrées ; conservation comptable à la charge des producteurs (export CSV).
- **Droits des personnes** (accès, rectification, effacement, opposition) exercables auprès de l'admin de l'instance et de chaque producteur — détaillé sur la page [Mentions légales](mentions-legales/) de chaque instance.

## Stack

Python 3.11+ · Django 5 · **PostgreSQL** (prod, champs JSONB pour les attributs personnalisés) / SQLite (dev et instance mono-espace) · Leaflet + **fond IGN Plan V2 sans clé** / ortho Esri · templates HTML/CSS sobres · déploiement WSGI (AlwaysData compatible)

## Démarrage rapide

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate   # les migrations sont versionnées dans le dépôt
python manage.py createsuperuser   # back-office /admin/
python manage.py runserver
```

## Déploiement

Voir [docs/DEPLOY_ALWAYSDATA.md](docs/DEPLOY_ALWAYSDATA.md) et les [décisions techniques](docs/DECISIONS.md).

## Licence

Logiciel libre sous **GNU AGPL-3.0** ([LICENSE](LICENSE) — version anglaise de référence) : déployez votre propre instance pour votre territoire, adaptez le code — toute instance publique modifiée doit partager ses modifications. Résumé en français : [LICENSE.fr.md](LICENSE.fr.md).

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md).