# Revue du parcours pro — itérations incrémentales par profils métier

Ce document est le **protocole** des itérations d'amélioration de l'espace pro.
Chaque itération suit le même cycle, sans exception :

1. **Périmètre** : un seul thème (ex. bandeau nav, saisies, catalogues, commandes).
2. **Audit des 5 profils EN PARALLÈLE** sur ce périmètre (voir fiches ci-dessous) :
   pour chaque profil, on déroule ses parcours critiques dans le code
   (templates, vues, vocabulaire `vocab` de l'activité, émojis, unités,
   médias héros) et on note frictions, incohérences, manques.
3. **Constats** : liste priorisée (impact × fréquence) par profil + constats transverses.
4. **Correctifs** : une PR par lot cohérent, branchée sur `dev`, fusionnée,
   puis propagée vers `main` au moment du déploiement. Chaque lot porte un
   numéro de revue CSS (V3.43, V3.44… inséré en région stable du append.css).
5. **Journal** : le rapport d'itération est publié en commentaire de l'issue
   GitHub correspondante (backlog ci-dessous), avec ce qui reste à faire.

**Priorité des périmètres** : (1) interface pro générale — bandeau nav,
fonctionnalités communes, saisies ; puis simulation métier par profil :
(2) fromager, (3) micro-brasseur, (4) foodtruck, (5) pizzéria italienne,
(6) maraîcher.

## Fiches personas (clients bêta types)

### 🧀 Fromager — producteur transformateur
- Activité : `FROMAGER`. Vocabulaire : fromages, unités la pièce / le kg,
  affinage. Parcours critiques : catalogue (crèmes, tommes, yaourts),
  publications saisonnières (production limitée, aléas d'affinage), points de
  livraison (marchés, AMAP).
- Points d'attention : prix au kg vs à la pièce, quantités entières,
  duplication des publications récurrentes, note de période (clairières
  saisonnières de production).

### 🍺 Micro-brasseur — producteur transformateur
- Activité : `MICRO_BRASSEUR`. Vocabulaire : bières, unités la pièce / le kg
  (malt), fûts. Parcours critiques : catalogues par gamme, publications des
  séries limitées, vitrine.
- Points d'attention : séries éphémères = duplication, prix fût vs bouteille,
  médias (photos de brasserie), émojis (🍺 déjà présent).

### 🚚 Foodtruck — restauration nomade
- Activité : `FOODTRUCK` (+ spécialité). Vocabulaire : plats, cartes (le
  `vocab` bascule recolte→carte). Parcours critiques : cartes vitrines
  hebdo, points d'arrêt (créneaux), duplication carte de semaine,
  modification à la volée avec le rythme du service.
- Points d'attention : réagencement graphique par catégorie, publication
  ultra-fréquente, mobile (édition depuis un téléphone sur le terrain).

### 🍕 Pizzéria italienne — restauration fixe
- Activité : `PIZZERIA` (mapping existant : RESTAURANT à spécialité PIZZERIA
  — vérifier le vocab). Parcours critiques : carte fixe (catalogue
  permanent), mise à jour des prix en masse, médias des plats.
- Points d'attention : édition massive (💾 tout enregistrer), cartes du jour
  dupliquées, harmonisation vitrine client, allergènes en descriptif.

### 🥕 Maraîcher — producteur végétal
- Activité : `MARAICHER` (profil historique, déjà bien servi). Parcours
  critiques : publications saisonnières hebdo, reprise des valeurs, grande
  liste de produits (40+), réordonnancement par catégorie de saison.
- Points d'attention : vitesse d'édition d'une longue liste, imports
  sélectifs, unités (botte, barquette), émojis devinés par mot-clé.

## Grille d'audit commune (appliquée à chaque profil)
- [ ] Arrivée : dashboard, bandeau, onboarding, vocabulaire cohérent
- [ ] Catalogues : création / import / édition rapide / duplication / activation
- [ ] Publications : création, saisie (y compris mobile), duplication,
      publication / dépublication, note de période
- [ ] Vocabulaire de l'information : libellés qui parlent le métier,
      données d'exemple crédibles pour l'activité ?
- [ ] Ergonomie : clics gaspillés, raccourcis, sauvegarde, feedback
- [ ] Harmonisation : le rendu pro reflète-t-il la vitrine client ?
      (mêmes catégories, émojis, médias, hiérarchie)
- [ ] Mobile : édition utilisable sur petit écran ?
