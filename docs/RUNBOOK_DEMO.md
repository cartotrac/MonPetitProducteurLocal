# 🧪 Runbook — Jeu de démonstration MPPL

> Objectif : une instance capable de **montrer le portail de bout en
> bout pour chaque métier** (maraîcher, arboriculteur, éleveur,
> fromager, apiculteur, micro-brasseur, conserverie, foodtruck,
> traiteur, restaurant) sans dépendre d'un historique de production.

Le jeu de démo couvre **100 espaces fictifs** (Tarn et limitrophes,
Bretagne, Loire, Corse, La Réunion, Martinique + pros régionaux
diversifiés) : catalogues multi-catégories par métier, points de
livraison et créneaux **géolocalisés**, récolte de la semaine publiée +
semaine à venir « à publier », cartes/boutiques, commandes et paniers
dans tous les statuts, et depuis ce runbook **vitrines complètes**
(blocs À propos, Horaires, FAQ, mini-carte).

---

## 1. Cas A — Recharger la démo sur l'instance de prod (le plus courant)

Depuis la racine du projet sur le serveur AlwaysData :

```bash
bash scripts/deploy_prod.sh --demo
```

Le script enchaîne déjà : code (fetch + reset dur sur `origin/main`),
dépendances, sauvegarde de la base, `check` / `migrate` /
`collectstatic`, puis **purge + repeuplement** de la démo :

```bash
venv/bin/python manage.py peupler_demo --purge
venv/bin/python manage.py peupler_demo
venv/bin/python manage.py simuler_stats_demo
```

puis redémarre le site WSGI (API AlwaysData si `AD_API_KEY` /
`AD_SITE_ID` sont définies, sinon le faire depuis le panneau) et
rappelle le Ctrl+Shift+R.

> ⚠️ `peupler_demo --purge` supprime **uniquement** les comptes de démo
> (`demo.*` + espaces marqués démo). Les comptes réels sont conservés.

## 2. Cas B — Frais d'installation (base vierge)

L'ordre importe ; depuis la racine :

```bash
venv/bin/python manage.py migrate
venv/bin/python manage.py charger_catalogues_activites   # charge le fixture maraîcher si absent
venv/bin/python manage.py peupler_demo                   # idempotent
venv/bin/python manage.py simuler_stats_demo             # graphes home sur 30 j
venv/bin/python manage.py collectstatic --noinput
```

Le catalogue maraîcher historique (`produits_standard.json`) est
désormais **chargé automatiquement** par `charger_catalogues_activites`
quand la base n'en contient aucune trace : l'ordre « migrate →
charger → peupler » ne dépend plus d'un `loaddata` manuel oublié
(c'était le trou du runbook : sans lui, les fermes maraîchères
naissaient avec un catalogue vide et le peuplement s'interrompait).

## 3. Options de `peupler_demo`

| Option | Effet |
|--------|-------|
| *(aucune)* | idempotent : crée ce qui manque, ignore ce qui existe, **rattrape les modules vitrine vides** |
| `--purge` | supprime tous les comptes de démo puis s'arrête |
| `--reset-commandes-demo` | efface commandes/paniers des SEULS espaces démo et les régénère (rafraîchit « la semaine ») |
| `--reset-commandes` | PONCTUEL : efface TOUTES les commandes/paniers (comptes réels inclus) |
| `--reset-complet` | grand nettoyage : purge démo + données de tous les comptes, puis repeuple |

Rafraîchir « la semaine de démo » avant une démo client :
`peupler_demo --reset-commandes-demo` (les récoltes reprennent la
semaine en cours, les commandes redeviennent « à valider »).

## 4. Modules vitrine (À propos, Horaires, FAQ, mini-carte)

`peupler_demo` remplit désormais `ParametresVitrine.modules` pour
**chaque espace de démo** :

- **À propos** : texte de la fiche + mention « espace de
  démonstration » ;
- **Horaires** : déduits des **créneaux réels** de l'espace
  (jour, heures, point de livraison) — toujours cohérents avec ce que
  la vitrine affiche par ailleurs ;
- **FAQ** : deux questions génériques (commande, retrait) ;
- **mini-carte** : activée (les 100 espaces sont géolocalisés).

Un **rattrapage** s'applique aussi aux espaces de démo plus anciens :
tout espace marqué démo dont `modules` est vide reçoit ce jeu au
prochain `peupler_demo` (sans option). Les espaces dont le gérant a
déjà personnifié ses modules ne sont **jamais écrasés**.

## 5. Vérifications post-déploiement

```bash
# tous les espaces démo ont leurs modules vitrine
venv/bin/python manage.py shell -c "
from portal.models import ParametresVitrine
v = ParametresVitrine.objects.filter(exploitant__est_demo=True)
print('modules remplis :', sum(1 for x in v if x.modules), '/', v.count())"
```

Puis dans le navigateur (Ctrl+Shift+R) :

- vitrine maraîcher : `/exploitant/les-jardins-du-sor/` → blocs
  « À propos », « Horaires », « Questions fréquentes » et mini-carte
  présents, badge 🧪 DÉMO visible ;
- vitrine d'un autre métier (ex. fromager) : même contrôle ;
- recherche `/recherche/` → 100 espaces sur la carte Leaflet ;
- une commande passée depuis la vitrine apparaît côté pro.

## 6. Comptes d'essai (mot de passe unique : `demo1234!`)

| Profil | Comptes représentatifs |
|--------|------------------------|
| Maraîcher | `demo.maraicher`, `demo.albi.maraicher`, `demo.castres.maraicher` |
| Arboriculteur | `demo.vergers`, `demo.arboriculteur`, `demo.gaillac.arboriculteur` |
| Fromager | `demo.fromager`, `demo.albi.fromager`, `demo.castres.fromager` |
| Apiculteur | `demo.apiculteur`, `demo.apiculteur.lavaur`, `demo.castres.apiculteur` |
| Éleveur | `demo.eleveur`, `demo.aveyron.eleveur`, `demo.corse.eleveur` |
| Micro-brasseur | `demo.albi.microbrasseur`, `demo.brasserie.sor`, `demo.brasserie.leguer` |
| Conserverie | `demo.conserverie`, `demo.castres.conserverie`, `demo.bretagne.conserverie` |
| Foodtruck | `demo.foodtruck`, `demo.foodtruck.crepes.gaillac`, `demo.albi.foodtruck.pizza` |
| Traiteur | `demo.traiteur`, `demo.traiteur.gaillac`, `demo.albi.traiteur` |
| Restaurant | `demo.restaurant`, `demo.albi.restaurant`, `demo.annecy.restaurant` |
| Client | `demo.public` (Camille Public), `demo.client`, `demo.cliente` |

> ⚠️ Toutes les données de démo sont FICTIVES : noms, SIRET (valides au
> format Luhn mais inventés), adresses et coordonnées ne référencent
> aucune entreprise réelle.
