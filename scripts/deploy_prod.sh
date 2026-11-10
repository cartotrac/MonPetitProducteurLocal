#!/usr/bin/env bash
# Déploiement de MonPetitProducteurLocal sur AlwaysData (mppl.cartotrac.fr).
#
# Usage, depuis la racine du projet sur le serveur :
#   bash scripts/deploy_prod.sh           # mise à jour standard
#   bash scripts/deploy_prod.sh --demo    # + recharge des espaces de DÉMO
#
# Le script :
#   1. supprime l'ancien dossier portal/migrations local NON VERSIONNÉ
#      — sans ça, git pull refuse la mise à jour ;
#   2. tire le code (git pull) ;
#   3. met à jour les dépendances (requirements.txt) ;
#   4. sauvegarde la base AVANT toute migration — pg_dump (PostgreSQL)
#      ou copie du fichier SQLite — dans backups/ ;
#   5. lance check, migrate (RENAME COLUMN etc.), collectstatic ;
#   6. recharge éventuellement les espaces de démonstration (--demo) ;
#   7. redémarre le site WSGI (API AlwaysData si AD_API_KEY/AD_SITE_ID
#      sont définies, sinon rappel pour le faire depuis le panneau).
set -euo pipefail

cd "$(dirname "$0")/.."

if ! venv/bin/python -V >/dev/null 2>&1; then
  echo "ERREUR : le virtualenv venv/ est absent ou cassé — son" >&2
  echo "interpréteur Python n'existe plus. Recréez-le puis relancez :" >&2
  echo "  python3 -m venv venv" >&2
  echo "  venv/bin/pip install -r requirements.txt" >&2
  echo "  venv/bin/pip install \"psycopg[binary]\"" >&2
  exit 1
fi

DEMO=0
for arg in "$@"; do
  case "$arg" in
    --demo) DEMO=1 ;;
    *) echo "Option inconnue : $arg (usage : --demo)" >&2; exit 1 ;;
  esac
done

echo "==> 1/7 Suppression de l'ancien dossier migrations local"
rm -rf portal/migrations

echo "==> 2/7 Récupération du code"
git pull
git checkout -- portal/migrations 2>/dev/null || true

echo "==> 3/7 Dépendances"
venv/bin/pip install -q -r requirements.txt

echo "==> 4/7 Sauvegarde de la base"
mkdir -p backups
HORODAGE=$(date +%Y%m%d_%H%M%S)
if [ -f .env ] && grep -q "^DB_ENGINE=django.db.backends.postgresql" .env; then
  if ! command -v pg_dump >/dev/null 2>&1; then
    echo "   ERREUR : pg_dump introuvable — sauvegardez la base à la main avant de relancer." >&2
    exit 1
  fi
  set -a; . ./.env; set +a
  PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -p "${$DB_PORT:-5432}" -U "$DB_USER" "$DB_NAME" \
    | gzip > "backups/db_$HORODAGE.sql.gz"
  echo "   sauvegarde PostgreSQL : backups/db_$HORODAGE.sql.gz"
elif [ -f db.sqlite3 ]; then
  cp db.sqlite3 "backups/db_$HORODAGE.sqlite3"
  echo "   copie SQLite : backups/db_$HORODAGE.sqlite3"
else
  echo "   AVERTISSEMENT : base introuvable, aucune sauvegarde faite."
fi

echo "==> 5/7 Contrôle Django + migrations + statiques"
venv/bin/python manage.py check
venv/bin/python manage.py migrate
venv/bin/python manage.py collectstatic --noinput

if [ "$DEMO" = "1" ]; then
  echo "==> Recharge des espaces de DÉMONSTRATION"
  venv/bin/python manage.py peupler_demo --purge
  venv/bin/python manage.py peupler_demo
  venv/bin/python manage.py simuler_stats_demo
  echo "   identifiants : demo.<metier> / demo1234!"
fi

echo "==> 6/7 Redémarrage WSGI"
# Toujours redémarrer : le code Python est chargé en mémoire.
if [ -n "${$AD_API_KEY:-}" ] && [ -n "${$AD_SITE_ID:-}" ]; then
  curl -s -u "$AD_API_KEY:" -X POST "https://api.alwaysdata.com/v1/site/$AD_SITE_ID/restart/"
  echo "   site AlwaysData redémarré via l'API"
else
  echo "   PENSER À REDÉMARRER LE SITE WSGI depuis le panneau AlwaysData :"
  echo "   Web > Sites > mppl.cartotrac.fr > Redémarrer."
fi

echo "==> 7/7 Terminé — rechargement dur du navigateur : Ctrl+Shift+R"
