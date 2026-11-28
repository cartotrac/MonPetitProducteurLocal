# Procédure de rollback (production AlwaysData)

Objectif : revenir à la fusion précédente de `main` si un déploiement
pose problème. `main` reste toujours déployable (voir
[CONTRIBUTING_VOLETS.md](CONTRIBUTING_VOLETS.md)) : un rollback est un
retour à la fusion d'avant, rien d'autre.

## 1. Identifier la version saine

```bash
git fetch origin
git log --oneline origin/main | head -5   # repérer la fusion précédente
```

Noter le SHA de la fusion à rejoindre.

## 2. Revenir en arrière côté code

Deux approches, au choix :

- **Revert (recommandé)** : crée une nouvelle fusion qui annule la
  précédente, historique conservé, rien de forcé.

  ```bash
  git checkout main && git pull
  git revert -m 1 <SHA-de-la-fusion-à-annuler>
  git push origin main
  ```

- **Reset (exceptionnel, si personne d'autre n'a poussé depuis)** :

  ```bash
  git checkout main && git pull
  git reset --hard <SHA-de-la-fusion-saine>
  git push --force-with-lease origin main
  ```

## 3. Redéployer

```bash
bash scripts/deploy_prod.sh
# puis relancer l'application WSGI (panneau AlwaysData) et
# Ctrl+Shift+R dans le navigateur.
```

## 4. Base de données : la règle de prudence

- Le schéma ne **descend** jamais automatiquement : une migration
  appliquée reste en place (le code précédent fonctionne avec, les
  migrations du projet sont conçues pour ne rien supprimer).
- Avant tout rollback, vérifier si la livraison annulée ajoutait une
  migration : `git show <SHA> --stat -- '*migrations*'`. Si oui,
  vérifier que la version saine démarre avec ce schéma (c'est la
  norme du projet : ajouts de champs nullables ou avec défaut).
- **Sauvegarde AlwaysData avant l'opération** (export de la base depuis
  le panneau) : elle couvre le cas inverse (rollback puis retour
  en avant).

## 5. Médias et fichiers

`media/` (logos, photos) et le `.env` ne sont jamais touchés par le
déploiement ni par un rollback : rien à faire de ce côté.

## 6. Après le rollback

- Commenter sur l'issue de suivi : version revenue en arrière, motif,
  correctif prévu.
- Reprendre sur la branche volet concernée : corriger, puis refaire
  une PR volet → `dev` → `dev` → `main` normale. Un rollback n'est
  jamais un abandon : la fusion annulée repart corrigée.
