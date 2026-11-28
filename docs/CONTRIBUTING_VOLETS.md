# Contribuer par volets parallèles

Mode opératoire pour faire avancer plusieurs chantiers d'amélioration
en parallèle, sans conflits de fusion. Complément du
[runbook de démo](RUNBOOK_DEMO.md) et du
[guide de contribution](../CONTRIBUTING.md) : ici on ne parle que de
l'organisation du travail.

## 1. Le principe : des volets à fichiers disjoints

Deux volets ne doivent pas toucher les mêmes fichiers en même temps.
C'est la règle unique qui rend la parallélisation possible.

| Volet | Fichiers principaux | Compatible en parallèle avec |
|-------|---------------------|------------------------------|
| Carte & géo | `static/js/search-map.js`, `landing-map.js`, `carte-points.js`, `pick-map.js` | tous les autres |
| CSS / charte | `static/css/append.css` (source seule) | tous les autres |
| Vitrine publique | `templates/portal/producer_detail.html`, `order_create.html` | espace pro, carte, messagerie |
| Espace pro | `templates/portal/pro/*`, `portal/forms.py` | vitrine publique, carte, CSS |
| Messagerie (e-mails, SMS) | helpers `_connexion_email` / `_envoyer_*`, `envoyer_sms`, panneau messagerie | tous les autres |
| Docs & runbook | `docs/*` | tous (jamais de conflit) |

Cas limite : `portal/views.py` est partagé par presque tous les volets.
Les règles qui suivent (branches longues, zones réservées, petites PR)
rendent le partage possible ; si deux volets doivent chacun y faire un
gros chantier, décale l'un des deux.

## 2. Une branche de longue durée par volet

```
main ──▶ dev ──▶ (PR dev → main, une par livraison)
              ▲
              ├── volet/carte        ──▶ petites PR vers dev
              ├── volet/messagerie   ──▶ petites PR vers dev
              └── volet/vitrine      ──▶ petites PR vers dev
```

- Une branche `volet/<nom>` vit le temps du chantier (semaines).
- **Une intention = une petite PR** de la branche volet vers `dev`.
- Après chaque fusion d'une PR d'un autre volet, fusionner `dev` dans
  sa branche volet (`git merge dev`) : on absorbe les évolutions au
  fil de l'eau au lieu d'accumuler des conflits.
- Jamais de PR volet → volet : chaînes de dépendances impossibles à
  trier. `dev` est le seul intégrateur, et il reste toujours
  déployable.
- Une fois le chantier terminé, la branche volet se supprime.

## 3. Git worktree : plusieurs volets ouverts en même temps

Sur une seule machine, sans `stash` ni `checkout` :

```bash
git worktree add ../mppl-carte volet/carte
git worktree add ../mppl-messagerie volet/messagerie
```

Chaque dossier est un checkout complet sur sa branche : on y lance un
serveur de dev Django sur un port distinct (deux `runserver 127.0.0.1:8001`,
`:8002`…), avec sa propre base. On passe de l'un à l'autre librement.

## 4. Pratiques anti-conflit

- **Petites PR, une intention** : un correctif = une PR. La fusion de
  fichiers massifs (`views.py` > 300 ko) ne reste indolore qu'ainsi.
- **Zones réservées** : chacun ajoute ses nouveaux helpers près de ses
  voisins thématiques (ex. un helper d'e-mail à côté de
  `_connexion_email`), jamais en fin de fichier.
- **Fichiers minifiés jamais édités à la main** : `.min.css` et
  `.min.js` sont régénérés par `scripts/optimiser_css.py`. En cas de
  conflit sur un `.min`, fusionner la source, relancer le script,
  committer le résultat. C'est la résolution documentée des conflits
  sur ces fichiers.
- Le hook pre-commit (rappel CSS minifiés) reste installé dans
  chaque worktree : `scripts/install_hooks.sh`.

## 5. Cadence d'intégration et de déploiement

1. PR volet → `dev`, revue, fusion dès qu'elle est verte.
2. Une PR `dev` → `main` par livraison (ou par semaine).
3. Déploiement : `bash scripts/deploy_prod.sh`, restart WSGI,
   Ctrl+Shift+R (voir le runbook).
4. `main` reste toujours déployable : un rollback est un retour à
   la fusion précédente, rien d'autre.

## 6. Suivi

L'issue de suivi (journal des lots) reçoit un commentaire par
livraison, comme depuis le lot 5. Pour piloter le parallélisme, trois
colonnes suffisent, à tenir sur l'issue ou dans un GitHub Project :

- **Prêt** : chantier spécifié, personne dessus ;
- **En cours (volet X)** : branche volet existante, qui y travaille ;
- **Livré** : fusionné sur `main`, déployé.

Avant de démarrer une session, lire ce tableau : on ne démarre jamais
un chantier déjà « En cours » ailleurs.

## 7. Volets parallèles identifiés (post-lot 10)

1. **Messagerie** : L2 (SMS réel via la passerelle Free Mobile),
   e-mail au client quand le panier passe en « prêt ».
2. **Carte** : agrégation visuelle des marchés en mode All-in-1,
   optimisation du chargement des couches administratives.
3. **Docs & qualité** : scripts de tests à froid des parcours clés
   versionnés dans `scripts/tests_locaux/`, procédure de rollback.

Ils sont disjoints en fichiers : trois branches, trois PR, aucune
collision.
