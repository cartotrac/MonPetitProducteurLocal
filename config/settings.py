import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# Charge le fichier .env à la racine du projet s'il existe (dev / déploiement
# AlwaysData en SSH). En WSGI, les variables du panneau priment (setdefault :
# l'environnement déjà défini gagne sur le fichier).
def _charger_env(chemin=BASE_DIR / ".env"):
    if not chemin.exists():
        return
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        os.environ.setdefault(cle.strip(), valeur.strip())


_charger_env()


def env(key, default=None):
    return os.environ.get(key, default)


# --- Durcissement (audit sécurité, lot 1) : DEBUG désactivé par
# défaut, SECRET_KEY obligatoire en production, HTTPS forcé derrière
# le proxy AlwaysData, cookies session/CSRF en Secure, HSTS un an. ---
DEBUG = env("DJANGO_DEBUG", "0") == "1"

from django.core.exceptions import ImproperlyConfigured  # noqa: E402

SECRET_KEY = env("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-insecure-key-change-me"
    else:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY est requis en production : définissez-la "
            "dans le .env ou le panneau AlwaysData.")

ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

# HTTPS derrière le proxy AlwaysData : le portail n'est servi qu'en
# https ; en dev (DEBUG), les cookies restent utilisables en http.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = (not DEBUG) and (env("DJANGO_SSL_REDIRECT", "1") == "1")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # « Continuer avec Google » (django-allauth) : inscription et
    # connexion OAuth en 1 clic — le bouton n'est affiché que si
    # GOOGLE_CLIENT_ID est renseigné (.env / panneau AlwaysData).
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "portal.apps.PortalConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Exploitation gérée par le compte courant (propriétaire ou
                # membre de l'équipe) : naviguation et menus partagés.
                "portal.context.exploitant_contexte",
                "portal.context.instance_contexte",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# L'aperçu de la vitrine dans le dashboard est une iframe du même domaine :
# autoriser l'affichage same-origin (le DENY par défaut bloquait l'aperçu).
X_FRAME_OPTIONS = "SAMEORIGIN"

# CSRF : en https, Django vérifie l'en-tête Origin du navigateur contre la
# liste des origines de confiance. Renseigner dans .env l'URL exacte du site,
# avec scheme et domaine : ex. https://monpetitmaraicher.cartotrac.fr
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in env("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# SQLite par défaut (dev / instance mono-ferme) ; PostgreSQL en prod (voir .env.example)
DATABASES = {
    "default": {
        "ENGINE": env("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": env("DB_NAME", str(BASE_DIR / "db.sqlite3")),
        "USER": env("DB_USER", ""),
        "PASSWORD": env("DB_PASSWORD", ""),
        "HOST": env("DB_HOST", ""),
        "PORT": env("DB_PORT", ""),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---- « Continuer avec Google » (django-allauth) ----
# Client ID et secret OAuth (console.cloud.google.com) dans .env :
# sans GOOGLE_CLIENT_ID, le bouton Google n'est pas affiché. URI de
# redirection à déclarer chez Google :
#   https://mppl.cartotrac.fr/comptes/google/login/callback/
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", "")
GOOGLE_SECRET = env("GOOGLE_SECRET", "")
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
SITE_ID = 1
# Le flux Google crée/connecte directement (auto-signup : l'e-mail est
# vérifié par Google, la photo de profil Google préremplit
# ProfilClient.photo_url via l'adaptateur). Les inscriptions maison
# (e-mail + mot de passe) restent gérées par les vues du portail.
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_USERNAME_REQUIRED = False
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
# Un Localien déjà inscrit avec son e-mail Gmail (mot de passe maison)
# est connecté directement par Google, sans double compte.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_LOGIN_ON_EMAIL = True
SOCIALACCOUNT_ADAPTER = "portal.adapters.PortailSocialAdapter"
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {"client_id": GOOGLE_CLIENT_ID,
                "secret": GOOGLE_SECRET},
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
}

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"

# Admin de l'instance : affiché en pied de page (logo distant + nom
# cliquable) et sur la page des mentions légales.
INSTANCE_ADMIN = {
    "nom": "CartOtraC",
    "url": "https://www.cartotrac.fr",
    "logo": "https://www.cartotrac.fr/assets/img/porteurs/logos/CartOtraC.png",
}
USE_I18N = True
USE_TZ = True

# Fichiers statiques du projet (CSS, JS) : collectstatic les copie vers
# STATIC_ROOT (staticfiles/), servi en production par les « chemins
# statiques » du panneau AlwaysData (/static/ -> staticfiles) avec, en
# repli, le service Django de config/urls.py. Les URLs DOIVENT commencer
# par un slash : sinon les liens statiques deviennent relatifs à la page
# courante et cassent sur les pages profondes (/espace-pro/...).
# Après chaque modification de static/ :
#   manage.py collectstatic --noinput  puis redemarrer le site.
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# E-mails sortants (issue #3). Sans EMAIL_HOST, Django journalise au lieu
# d'envoyer (backend console) et l'interface en informe l'exploitant.
# AlwaysData : EMAIL_HOST=localhost (SMTP mutualisé) fonctionne aussi.
if env("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = int(env("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = env("EMAIL_USE_TLS", "0") == "1"
    EMAIL_USE_SSL = env("EMAIL_USE_SSL", "0") == "1"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL",
                         "noreply@monpetitmaraicher.cartotrac.fr")

LOGIN_URL = "/comptes/connexion/"
LOGIN_REDIRECT_URL = "/apres-connexion/"
LOGOUT_REDIRECT_URL = "/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Fichiers uploadés : 2 Mo max (logos et photos produits)
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
