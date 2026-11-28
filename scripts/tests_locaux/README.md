# Tests à froid des parcours clés

Ce dossier (volet « docs & qualité ») versionne les tests de parcours
exécutés avant chaque livraison : ils reconstruisent une base sqlite
jetable, sèment deux espaces (maraîcher et foodtruck) et vérifient
les parcours de bout en bout, sans réseau ni écriture hors du dossier.

## Exécution

Depuis la racine du dépôt, avec les dépendances du `requirements.txt`
installées :

```bash
python3 scripts/tests_locaux/test_parcours.py
```

- Code de sortie `0` : tout passe. `1` : au moins un échec (lignes
  « KO »).
- La base `base_test.sqlite3` est créée puis supprimée à chaque
  exécution ; les e-mails sont captés en mémoire (backend locmem),
  rien ne part réellement.

## Ce que couvre `test_parcours.py`

1. Vitrines publiques (carte du moment, bloc « Nous trouver »,
   bandeau des créneaux).
2. Commande client + e-mail de confirmation (dont : la commande
   survit à un échec SMTP).
3. Panier passé en « prêt » + notification e-mail au client.
4. Page de recherche : données de la carte présentes, clustering câblé.

## Pourquoi le schéma portal est créé « à la main »

La migration initiale de `portal` est spécifique PostgreSQL (elle est
appliquée en production, jamais rejouable sur sqlite). Le script marque
donc `migrate portal --fake` puis crée les tables via
`connection.schema_editor().create_model()` : le modèle est la source
de vérité, la base de test reste fidèle sans migrations sqlite.

## Ajouter un parcours

Ajoutez une section numérotée dans `test_parcours.py` avec des
`check(nom, condition)` : chaque vérification apparaît au bilan final.
Un échec de test ne doit jamais refléter un problème d'environnement
(réseau, SMTP) : on simule les services (locmem, stubs) pour ne tester
que le portail lui-même.
